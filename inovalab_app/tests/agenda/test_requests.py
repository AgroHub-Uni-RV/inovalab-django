from inovalab_app.tests.agenda.helpers import make_service, make_booking, service_data, service_web_data
from inovalab_app.tests.http import close_response
from datetime import date, time, datetime, timedelta
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Group
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase, override_settings
from django.test import Client
from rest_framework.test import APIClient

from inovalab_app.agenda import services
from inovalab_app.agenda.models import AgendaEquipamento, BOOKING_MODELS, AgendaServico
from inovalab_app.agenda.selectors import calendar_weeks, visible_bookings
from inovalab_app.catalogo.models import Equipamento, Servico
from inovalab_app.materiais.models import Material
from inovalab_app.tests.conteudo.helpers import image_upload


class BookingRequestFixtures:
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_user('avaliador')
        cls.admin.groups.add(Group.objects.get(name='Administradores'))
        cls.user = get_user_model().objects.create_user('solicitante', is_staff=True)
        cls.other = get_user_model().objects.create_user('outro', is_staff=True)
        cls.service = make_service()
        cls.machine = Equipamento.objects.create(nome='Máquina para pedido')
        cls.material = Material.objects.create(nome='PLA pedido', categoria='Filamento', quantidade=500,
                                               unidade='g', fonte='Laboratório')
        cls.data = service_data(prazo=datetime.fromisoformat('2026-11-01T15:00:00-03:00'))

    def create(self, actor=None, **overrides):
        return services.save_booking(actor=actor or self.user, data={**self.data, **overrides})

    def review(self, booking, decision='aprovar', actor=None, version=1):
        return services.review_booking(actor=actor or self.admin, category=booking.categoria, booking_id=booking.pk,
                                       expected_version=version, decision=decision,
                                       task_data={'descricao': 'Executar serviço', 'responsaveis': [self.user]})

    def create_confirmed(self, **overrides):
        return self.review(self.create(actor=self.admin, **overrides))


class BookingRequestTests(BookingRequestFixtures, TestCase):
    def test_normal_creation_is_pending_and_owned(self):
        try:
            booking = self.create()
        except PermissionDenied:
            self.fail('Usuário ativo deve conseguir solicitar um agendamento.')
        self.assertEqual((booking.situacao, booking.criado_por_id), ('pendente', self.user.pk))
        self.assertIsNone(booking.avaliado_em)
        self.assertEqual(list(visible_bookings(self.user)), [booking])
        self.assertEqual(list(visible_bookings(self.other)), [])
        self.assertEqual(booking.eventos.get().ator_id, self.user.pk)

    def test_pending_requests_do_not_block_confirmed_creation_or_calendar(self):
        first = self.create()
        self.create(actor=self.other)
        confirmed = self.create_confirmed()
        days = [day for week in calendar_weeks(visible_bookings(self.admin), '2026-11') for day in week]
        self.assertEqual(sum(day['count'] for day in days), 1)
        self.assertEqual([booking.pk for day in days for booking in day['bookings']], [confirmed.pk])
        first.refresh_from_db()
        self.assertEqual(first.situacao, 'pendente')

    def test_pending_request_can_be_created_over_existing_confirmed_booking(self):
        self.create_confirmed()
        self.assertEqual(self.create().situacao, 'pendente')

    def test_approval_reserves_and_records_decision_without_changing_owner(self):
        booking = self.create()
        saved = self.review(booking)
        self.assertEqual((saved.situacao, saved.versao, saved.criado_por_id, saved.avaliado_por_id),
                         ('confirmado', 2, self.user.pk, self.admin.pk))
        self.assertIsNotNone(saved.avaliado_em)
        event = saved.eventos.first()
        self.assertEqual((event.acao, event.ator_id), ('aprovar', self.admin.pk))
        self.assertEqual(event.alteracoes['situacao'], {'anterior': 'pendente', 'novo': 'confirmado'})
        self.assertEqual(self.create(actor=self.admin).situacao, 'pendente')

    def test_same_deadline_does_not_block_approval_of_independent_requests(self):
        booking = self.create()
        other = self.create_confirmed()
        saved = self.review(booking)
        self.assertEqual(saved.situacao, 'confirmado')
        self.assertNotEqual(saved.servico_id, other.servico_id)
        self.assertEqual(saved.eventos.count(), 2)

    def test_rejection_remains_visible_without_reserving_or_requiring_free_slot(self):
        booking = self.create()
        self.create_confirmed()
        saved = self.review(booking, 'rejeitar')
        self.assertEqual((saved.situacao, saved.versao), ('rejeitado', 2))
        self.assertIn(saved, visible_bookings(self.user))
        self.assertEqual(saved.eventos.first().acao, 'rejeitar')

    def test_decisions_are_admin_only_and_cannot_be_repeated(self):
        booking = self.create()
        for actor in (self.user, self.other, AnonymousUser()):
            with self.assertRaises(PermissionDenied):
                self.review(booking, actor=actor)
        self.review(booking, 'rejeitar')
        for version in (1, 2):
            with self.assertRaises(services.BookingConflict):
                self.review(booking, version=version)
        self.assertEqual(booking.eventos.count(), 2)

    def test_invalid_decision_and_stale_or_invalid_versions_do_not_change_request(self):
        booking = self.create()
        with self.assertRaises(ValidationError):
            self.review(booking, decision='confirmado')
        for version in (None, True, '1', 0):
            with self.assertRaises(ValidationError):
                self.review(booking, version=version)
        services.save_booking(actor=self.admin, category=booking.categoria, booking_id=booking.pk, expected_version=1,
                              data={'descricao': 'Pedido corrigido pelo administrador'})
        with self.assertRaises(services.BookingConflict):
            self.review(booking)
        booking.refresh_from_db()
        self.assertEqual((booking.situacao, booking.versao), ('pendente', 2))

    def test_normal_user_can_cancel_own_but_cannot_edit_or_assign_protected_fields(self):
        booking = self.create()
        with self.assertRaises(PermissionDenied):
            services.save_booking(actor=self.user, category=booking.categoria, booking_id=booking.pk, expected_version=1, data={'descricao': 'Editar'})
        services.cancel_booking(actor=self.user, category=booking.categoria, booking_id=booking.pk, expected_version=1)
        booking.refresh_from_db()
        self.assertIsNotNone(booking.cancelado_em)
        for field in ('situacao', 'criado_por', 'avaliado_por', 'avaliado_em'):
            with self.assertRaises(ValidationError):
                self.create(**{field: 'confirmado'})

    def test_anonymous_and_inactive_have_no_access(self):
        self.create()
        self.user.is_active = False
        for actor in (self.user, AnonymousUser()):
            self.assertFalse(bool(visible_bookings(actor)))
            with self.assertRaises(PermissionDenied):
                self.create(actor=actor)

    def test_spaces_cannot_be_reserved_by_any_role(self):
        for space_id in (1, 42):
            fields = {'categoria': 'espaco', 'objeto': space_id, 'material_proprio': None}
            for actor in (self.user, self.admin):
                with self.subTest(actor=actor), self.assertRaises(ValidationError):
                    self.create(actor=actor, **fields)

    def test_equipment_and_material_fields_are_rejected_on_service_request(self):
        for fields in ({'equipamentos': [self.machine.pk]}, {'material_gasto': self.material.pk}, {'material_proprio': True}):
            with self.assertRaises(ValidationError):
                self.create(**fields)
        self.assertEqual(AgendaServico.objects.count(), 0)

    def test_independent_services_can_be_approved_at_the_same_deadline(self):
        first, second = self.create(), self.create()
        self.assertEqual(self.review(first).situacao, 'confirmado')
        self.assertEqual(self.review(second).situacao, 'confirmado')

    def test_admin_creation_is_pending_without_evaluator(self):
        booking = self.create(actor=self.admin)
        self.assertEqual(booking.situacao, 'pendente')
        self.assertIsNone(booking.avaliado_por_id)


class BookingRequestInterfaceTests(BookingRequestFixtures, TestCase):
    def web_data(self, **overrides):
        return service_web_data(prazo_data='2026-11-01', prazo_hora='15:00', **overrides)

    def test_user_can_create_and_read_own_requests_without_admin_actions(self):
        self.client.force_login(self.user)
        response = self.client.post('/agenda/novo/', self.web_data())
        self.assertEqual(response.status_code, 302)
        booking = AgendaServico.objects.get()
        self.assertEqual((booking.situacao, booking.criado_por_id), ('pendente', self.user.pk))
        response = self.client.get(response.url)
        self.assertContains(response, 'Pendente')
        self.assertNotContains(response, 'Editar agendamento')
        self.assertContains(response, 'Cancelar agendamento')
        self.assertNotContains(response, '/avaliar/')
        self.assertEqual(self.client.get(f'/agenda/{booking.categoria}/{booking.pk}/historico/').status_code, 200)
        self.assertContains(self.client.get('/agenda/'), '/agenda/novo/')

    def test_owner_isolation_covers_pages_api_history_photo_and_filters(self):
        own = self.create()
        foreign = self.create(actor=self.other, descricao='SEGREDO de outro')
        self.client.force_login(self.user)
        response = self.client.get('/agenda/')
        self.assertEqual([booking.pk for booking in response.context['object_list']], [own.pk])
        self.assertNotContains(response, 'SEGREDO')
        self.assertEqual(self.client.get('/agenda/', {'q': 'SEGREDO'}).context['paginator'].count, 0)
        for suffix in ('', 'historico/', 'criador/foto/'):
            self.assertEqual(self.client.get(f'/agenda/{foreign.categoria}/{foreign.pk}/{suffix}').status_code, 404)
        api = APIClient()
        api.force_login(self.user)
        self.assertEqual(api.get('/api/v1/agendamentos/').data['count'], 1)
        self.assertEqual(api.get(f'/api/v1/agendamentos/{own.categoria}/{own.pk}/').status_code, 200)
        for suffix in ('', 'historico/'):
            self.assertEqual(api.get(f'/api/v1/agendamentos/{foreign.categoria}/{foreign.pk}/{suffix}').status_code, 404)

    def test_pending_and_rejected_outside_current_month_are_visible_and_filterable(self):
        pending = self.create()
        rejected = self.create(actor=self.user,
                               prazo=self.data['prazo'] - timedelta(days=70))
        self.review(rejected, 'rejeitar')
        self.client.force_login(self.user)
        response = self.client.get('/agenda/')
        self.assertEqual(set(b.pk for b in response.context['object_list']), {pending.pk, rejected.pk})
        self.assertEqual(sum(day['count'] for week in response.context['weeks'] for day in week), 0)
        response = self.client.get('/agenda/', {'situacao': 'rejeitado', 'mes': ''})
        self.assertEqual([b.pk for b in response.context['object_list']], [rejected.pk])
        self.assertContains(response, 'Rejeitado')
        self.assertEqual(self.client.get('/agenda/', {'mes': '2026-11'}).context['paginator'].count, 1)
        self.assertEqual(self.client.get('/agenda/', {'situacao': 'inventado'}).status_code, 400)

    def test_review_page_and_actions_are_admin_only_and_versioned(self):
        booking = self.create()
        self.client.force_login(self.user)
        self.assertEqual(self.client.get('/agenda/solicitacoes/').status_code, 403)
        url = f'/agenda/{booking.categoria}/{booking.pk}/avaliar/'
        self.assertEqual(self.client.post(url, {'versao': 1, 'decisao': 'aprovar'}).status_code, 403)
        self.assertEqual(self.client.get(f'/agenda/{booking.categoria}/{booking.pk}/editar/').status_code, 403)
        self.assertContains(self.client.get(f'/agenda/{booking.categoria}/{booking.pk}/cancelar/'), 'Confirmar cancelamento')
        self.client.force_login(self.admin)
        response = self.client.get('/agenda/solicitacoes/')
        self.assertEqual([row.pk for row in response.context['object_list']], [booking.pk])
        self.assertContains(response, url)
        self.assertNotContains(response, 'AgroHub')
        self.assertEqual(self.client.get(url).status_code, 405)
        confirm_url = f'/tarefas/confirmar-servico/{booking.pk}/'
        self.assertRedirects(self.client.post(url, {'versao': 1, 'decisao': 'aprovar'}), confirm_url)
        self.assertRedirects(self.client.post(confirm_url, {'agendamento_versao': 1,
            'descricao': 'Executar serviço', 'responsaveis': [self.user.pk],
            'materiais-TOTAL_FORMS': 0, 'materiais-INITIAL_FORMS': 0}), booking.get_absolute_url())
        self.assertContains(self.client.get(f'/agenda/{booking.categoria}/{booking.pk}/'), 'Confirmado')
        self.assertEqual(self.client.post(url, {'versao': 1, 'decisao': 'rejeitar'}).status_code, 409)
        confirmed = self.client.get('/agenda/solicitacoes/', {'status': 'confirmada'})
        self.assertEqual([row.pk for row in confirmed.context['object_list']], [booking.pk])
        self.assertNotContains(confirmed, 'value="aprovar"')

    def test_review_error_preserves_request_and_csrf_and_unknown_fields_are_rejected(self):
        booking = self.create()
        services.save_booking(actor=self.admin, category='servico', booking_id=booking.pk, expected_version=1, data={'observacoes': 'Alterado'})
        url = f'/agenda/{booking.categoria}/{booking.pk}/avaliar/'
        self.client.force_login(self.admin)
        self.assertEqual(self.client.post(url, {'versao': 1, 'decisao': 'aprovar'}).status_code, 409)
        self.assertEqual(self.client.post(url, {'versao': 1, 'decisao': 'rejeitar', 'criado_por': self.admin.pk}).status_code, 400)
        secure = Client(enforce_csrf_checks=True)
        secure.force_login(self.admin)
        self.assertEqual(secure.post(url, {'versao': 2, 'decisao': 'rejeitar'}).status_code, 403)
        self.assertRedirects(self.client.post(url, {'versao': 2, 'decisao': 'rejeitar'}), '/agenda/solicitacoes/')
        self.client.force_login(self.user)
        self.assertContains(self.client.get('/agenda/'), 'Rejeitado')

    def test_forged_space_submission_is_rejected_for_both_roles(self):
        space_id = 42
        for actor in (self.admin, self.user):
            self.client.force_login(actor)
            response = self.client.get('/agenda/novo/')
            self.assertNotContains(response, '<option value="espaco"')
            data = self.web_data(categoria='espaco', objeto=space_id)
            data.pop('material_proprio', None)
            response = self.client.post('/agenda/novo/', data)
            self.assertEqual(response.status_code, 200)
            self.assertIn('categoria', response.context['form'].errors)
        self.assertFalse(AgendaServico.objects.exists())

    def test_api_normal_creation_cannot_spoof_state_owner_or_manage_booking(self):
        api = APIClient()
        api.force_login(self.user)
        response = api.post('/api/v1/agendamentos/', self.data, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual((response.data['situacao'], response.data['criado_por']), ('pendente', self.user.pk))
        url = f'/api/v1/agendamentos/{response.data["categoria"]}/{response.data["id"]}/'
        for method in (api.patch, api.put):
            self.assertEqual(method(url, {'versao': 1}, format='json').status_code, 403)
        self.assertEqual(api.delete(url, {'versao': 1}, format='json').status_code, 204)
        for field in ('situacao', 'avaliado_por', 'avaliado_em', 'criado_por'):
            self.assertEqual(api.post('/api/v1/agendamentos/', {**self.data, field: 'confirmado'}, format='json').status_code, 400)
        space_id = 42
        self.assertEqual(api.post('/api/v1/agendamentos/', {**self.data, 'categoria': 'espaco',
            'objeto': space_id, 'material_proprio': None}, format='json').status_code, 400)

    def test_requests_link_moves_to_agenda_header_and_remains_role_scoped(self):
        self.client.force_login(self.user)
        response = self.client.get('/agenda/')
        self.assertContains(response, '/agenda/')
        self.assertNotContains(response, '/agenda/solicitacoes/')
        self.client.force_login(self.admin)
        agenda = self.client.get('/agenda/')
        self.assertContains(agenda, 'class="secondary-button" href="/agenda/solicitacoes/"')
        self.assertNotIn('/agenda/solicitacoes/', [item['href'] for item in agenda.context['nav_items']])
        html = agenda.content.decode()
        self.assertLess(html.index('class="secondary-button" href="/agenda/solicitacoes/"'),
                        html.index('class="primary-button" href="/agenda/novo/"'))
        response = self.client.get('/agenda/solicitacoes/')
        selected = [item['label'] for item in response.context['nav_items'] if item['current']]
        self.assertEqual(selected, ['Agendamentos'])

    def test_local_requests_page_includes_confirmed_bookings_and_counts(self):
        request = self.create()
        self.review(request)
        self.create_confirmed(prazo=self.data['prazo'] + timedelta(hours=1))
        self.client.force_login(self.admin)
        response = self.client.get('/agenda/solicitacoes/', {'situacao': '', 'mes': ''})
        self.assertEqual(response.context['paginator'].count, 2)
        self.assertEqual(response.context['stat_counts']['confirmada'], 2)
        self.assertContains(response, f'/agenda/{request.categoria}/{request.pk}/')
        self.assertContains(response, '>Confirmadas</a>')
        self.assertContains(response, 'task-column concluido')
        self.assertNotContains(response, 'value="aprovar"')

    def test_confirmed_tab_includes_three_categories_and_cancelled_are_separate(self):
        service = self.create_confirmed()
        equipment = AgendaEquipamento.objects.create(equipamento=self.machine, criado_por=self.admin, motivo='Uso confirmado', inicio=self.data['prazo']-timedelta(hours=1), fim=self.data['prazo'])
        visit = services.save_booking(actor=self.admin, data={
            'categoria': 'visita', 'quantidade_pessoas': 3, 'data': date(2026, 11, 1),
            'hora_inicio': time(14), 'hora_termino': time(15)})
        cancelled = self.create_confirmed(
                                prazo=self.data['prazo'] + timedelta(hours=1))
        services.cancel_booking(actor=self.admin, category='servico', booking_id=cancelled.pk, expected_version=2)
        self.client.force_login(self.admin)
        response = self.client.get('/agenda/solicitacoes/', {'status': 'confirmada'})
        self.assertEqual({(row.categoria, row.pk) for row in response.context['object_list']},
                         {(row.categoria, row.pk) for row in (service, equipment, visit)})
        self.assertEqual(response.context['stat_counts'],
                         {'all': 4, 'pendente': 0, 'confirmada': 3, 'cancelada': 1, 'recusada': 0})
        self.assertContains(response, 'booking-review-actions', count=3)
        self.assertContains(response, '>Cancelar</button>', count=3)
        self.assertNotContains(response, 'value="aprovar"')
        self.assertNotContains(response, 'value="rejeitar"')
        self.assertContains(response, 'aria-current="page">Confirmadas</a>')
        cancelled_page = self.client.get('/agenda/solicitacoes/', {'status': 'cancelada'})
        self.assertEqual([row.pk for row in cancelled_page.context['object_list']], [cancelled.pk])
        self.assertContains(cancelled_page, 'task-column canceladas')
        self.assertContains(cancelled_page, 'stat-card gray')

    def test_confirmed_tab_preserves_search_month_and_pagination(self):
        bookings = [self.create_confirmed(descricao=f'Confirmação pesquisável {index}',

                    prazo=self.data['prazo'] + timedelta(hours=index)) for index in range(27)]
        services.cancel_booking(actor=self.admin, category='servico', booking_id=bookings[0].pk, expected_version=2)
        self.create_confirmed(descricao='Confirmação pesquisável fora do mês',
                     prazo=self.data['prazo'] + timedelta(days=40))
        self.create(actor=self.user, descricao='Confirmação pesquisável pendente')
        self.client.force_login(self.admin)
        params = {'status': 'confirmada', 'mes': '2026-11', 'q': 'pesquisável', 'page': 2}
        response = self.client.get('/agenda/solicitacoes/', params)
        self.assertEqual((response.context['paginator'].count, len(response.context['object_list'])), (26, 1))
        self.assertEqual(response.context['stat_counts']['confirmada'], 26)
        self.assertEqual(response.context['stat_counts']['cancelada'], 1)
        self.assertTrue(all(row.situacao == 'confirmado' for row in response.context['object_list']))
        self.assertContains(response, 'mes=2026-11')
        self.assertContains(response, 'q=pesquis%C3%A1vel')
        self.assertContains(response, 'status=confirmada')
        self.assertNotContains(response, 'value="aprovar"')
        empty = self.client.get('/agenda/solicitacoes/', {'status': 'confirmada', 'mes': '2027-01'})
        self.assertContains(empty, 'Nenhuma reserva confirmada')

    def test_decision_pages_remain_readable_after_evaluator_account_is_deleted(self):
        booking = self.create()
        self.review(booking)
        self.admin.delete()
        self.client.force_login(self.user)
        self.assertContains(self.client.get(f'/agenda/{booking.categoria}/{booking.pk}/'), 'Conta removida')

    def test_dashboard_counts_only_own_confirmed_bookings(self):
        from inovalab_app.shared.dashboard import dashboard_context

        confirmed = self.create()
        self.review(confirmed)
        self.create(actor=self.other,  prazo=self.data['prazo'] + timedelta(hours=1))
        self.create( prazo=self.data['prazo'] + timedelta(hours=1))
        context = dashboard_context(self.user, now=self.data['prazo'] - timedelta(hours=1))
        days = [day for month in context['months'] for week in month['weeks'] for day in week if day['in_month']]
        self.assertEqual(sum(day['reservations'] for day in days), 1)

    def test_api_status_filters_and_pagination_never_include_other_users(self):
        for index in range(27):
            self.create(actor=self.user, descricao=f'Próprio {index}')
            self.create(actor=self.other, descricao='SEGREDO')
        api = APIClient()
        api.force_login(self.user)
        page = api.get('/api/v1/agendamentos/', {'situacao': 'pendente'}).data
        self.assertEqual((page['count'], len(page['results'])), (27, 25))
        self.assertTrue(all(b['criado_por'] == self.user.pk for b in page['results']))
        self.assertEqual(len(api.get('/api/v1/agendamentos/', {'page': 2}).data['results']), 2)
        self.assertEqual(api.get('/api/v1/agendamentos/', {'situacao': 'rejeitado'}).data['count'], 0)
        self.assertEqual(api.get('/api/v1/agendamentos/', {'situacao': 'inventado'}).status_code, 400)

    def test_normal_owner_photo_is_available_but_other_user_cannot_fetch_it(self):
        with TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            self.user.foto.save('solicitante.webp', image_upload(), save=True)
            booking = self.create()
            url = f'/agenda/{booking.categoria}/{booking.pk}/criador/foto/'
            self.client.force_login(self.user)
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertIn('no-store', response['Cache-Control'])
            close_response(response)
            self.client.force_login(self.other)
            self.assertEqual(self.client.get(url).status_code, 404)

    def test_admin_can_read_request_after_creator_account_is_deleted(self):
        booking = self.create()
        self.user.delete()
        self.client.force_login(self.admin)
        self.assertContains(self.client.get('/agenda/solicitacoes/'), booking.objeto_nome)
        self.assertEqual(self.client.get(f'/agenda/{booking.categoria}/{booking.pk}/').status_code, 200)
