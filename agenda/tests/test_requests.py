from datetime import datetime, timedelta
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Group
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase, override_settings
from django.test import Client
from rest_framework.test import APIClient

from agenda import services
from agenda.models import Agendamento
from agenda.selectors import calendar_weeks, visible_bookings
from catalogo.models import Equipamento, Servico
from materiais.models import Material
from conteudo.tests.helpers import image_upload


class BookingRequestFixtures:
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_user('avaliador')
        cls.admin.groups.add(Group.objects.get(name='Administradores'))
        cls.user = get_user_model().objects.create_user('solicitante', is_staff=True)
        cls.other = get_user_model().objects.create_user('outro', is_staff=True)
        cls.service = Servico.objects.first()
        cls.machine = Equipamento.objects.create(nome='Máquina para pedido')
        cls.material = Material.objects.create(nome='PLA pedido', categoria='Filamento', quantidade=500,
                                               unidade='g', fonte='Laboratório')
        cls.data = {'categoria': 'servico', 'objeto': cls.service.pk,
                    'motivo': 'Pedido próprio', 'material_proprio': True,
                    'inicio': datetime.fromisoformat('2026-11-01T14:00:00-03:00'),
                    'fim': datetime.fromisoformat('2026-11-01T15:00:00-03:00')}

    def create(self, actor=None, **overrides):
        return services.save_booking(actor=actor or self.user, data={**self.data, **overrides})

    def review(self, booking, decision='aprovar', actor=None, version=1):
        return services.review_booking(actor=actor or self.admin, booking_id=booking.pk,
                                       expected_version=version, decision=decision)


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
        confirmed = self.create(actor=self.admin)
        days = [day for week in calendar_weeks(visible_bookings(self.admin), '2026-11') for day in week]
        self.assertEqual(sum(day['count'] for day in days), 1)
        self.assertEqual([booking.pk for day in days for booking in day['bookings']], [confirmed.pk])
        first.refresh_from_db()
        self.assertEqual(first.situacao, 'pendente')

    def test_pending_request_can_be_created_over_existing_confirmed_booking(self):
        self.create(actor=self.admin)
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
        with self.assertRaises(services.BookingConflict):
            self.create(actor=self.admin)

    def test_approval_conflict_keeps_pending_and_does_not_record_decision(self):
        booking = self.create()
        self.create(actor=self.admin)
        with self.assertRaises(services.BookingConflict) as error:
            self.review(booking)
        self.assertEqual(error.exception.code, 'horario_ocupado')
        booking.refresh_from_db()
        self.assertEqual((booking.situacao, booking.versao, booking.eventos.count()), ('pendente', 1, 1))
        self.assertIsNone(booking.avaliado_em)

    def test_rejection_remains_visible_without_reserving_or_requiring_free_slot(self):
        booking = self.create()
        self.create(actor=self.admin)
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
        services.save_booking(actor=self.admin, booking_id=booking.pk, expected_version=1,
                              data={'motivo': 'Pedido corrigido pelo administrador'})
        with self.assertRaises(services.BookingConflict):
            self.review(booking)
        booking.refresh_from_db()
        self.assertEqual((booking.situacao, booking.versao), ('pendente', 2))

    def test_normal_user_cannot_edit_cancel_or_assign_protected_fields(self):
        booking = self.create()
        with self.assertRaises(PermissionDenied):
            services.save_booking(actor=self.user, booking_id=booking.pk, expected_version=1, data={'motivo': 'Editar'})
        with self.assertRaises(PermissionDenied):
            services.cancel_booking(actor=self.user, booking_id=booking.pk, expected_version=1)
        for field in ('situacao', 'criado_por', 'avaliado_por', 'avaliado_em'):
            with self.assertRaises(ValidationError):
                self.create(**{field: 'confirmado'})

    def test_anonymous_and_inactive_have_no_access(self):
        self.create()
        self.user.is_active = False
        for actor in (self.user, AnonymousUser()):
            self.assertFalse(visible_bookings(actor).exists())
            with self.assertRaises(PermissionDenied):
                self.create(actor=actor)

    def test_spaces_cannot_be_reserved_by_any_role(self):
        for space_id in (1, 42):
            fields = {'categoria': 'espaco', 'objeto': space_id, 'material_proprio': None}
            for actor in (self.user, self.admin):
                with self.subTest(actor=actor), self.assertRaises(ValidationError):
                    self.create(actor=actor, **fields)

    def test_approval_revalidates_target_machine_and_material_availability(self):
        for resource in (self.service, self.machine, self.material):
            booking = self.create(equipamentos=[self.machine.pk], material_proprio=False,
                                  material_gasto=self.material.pk, material_gasto_gramas=12)
            type(resource).objects.filter(pk=resource.pk).update(status='indisponivel')
            with self.assertRaises(ValidationError):
                self.review(booking)
            booking.refresh_from_db()
            self.assertEqual((booking.situacao, booking.eventos.count()), ('pendente', 1))
            type(resource).objects.filter(pk=resource.pk).update(status='disponivel')

    def test_adjacent_approval_and_optional_service_machines_preserve_reservation_rules(self):
        booking = self.create(equipamentos=[self.machine.pk])
        self.create(actor=self.admin, categoria='equipamento', objeto=self.machine.pk, material_proprio=None)
        self.review(booking)
        adjacent = self.create(inicio=self.data['fim'], fim=self.data['fim'] + timedelta(hours=1))
        self.assertEqual(self.review(adjacent).situacao, 'confirmado')

    def test_admin_and_legacy_direct_creation_are_confirmed_without_evaluator(self):
        booking = self.create(actor=self.admin)
        self.assertEqual(booking.situacao, 'confirmado')
        self.assertIsNone(booking.avaliado_por_id)
        legacy = Agendamento.objects.create(servico=self.service, motivo='Importado',
                                            inicio=self.data['inicio'], fim=self.data['fim'])
        self.assertEqual(legacy.situacao, 'confirmado')


class BookingRequestInterfaceTests(BookingRequestFixtures, TestCase):
    def web_data(self, **overrides):
        data = {key: value for key, value in self.data.items() if key not in ('inicio', 'fim')}
        return {**data, 'dia': '2026-11-01', 'hora_inicio': '14:00:00',
                'hora_termino': '15:00:00', 'material_proprio': 'sim', **overrides}

    def test_user_can_create_and_read_own_requests_without_admin_actions(self):
        self.client.force_login(self.user)
        response = self.client.post('/agenda/novo/', self.web_data())
        self.assertEqual(response.status_code, 302)
        booking = Agendamento.objects.get()
        self.assertEqual((booking.situacao, booking.criado_por_id), ('pendente', self.user.pk))
        response = self.client.get(response.url)
        self.assertContains(response, 'Pendente')
        self.assertNotContains(response, 'Editar agendamento')
        self.assertNotContains(response, 'Cancelar agendamento')
        self.assertNotContains(response, '/avaliar/')
        self.assertEqual(self.client.get(f'/agenda/{booking.pk}/historico/').status_code, 200)
        self.assertContains(self.client.get('/agenda/'), '/agenda/novo/')

    def test_owner_isolation_covers_pages_api_history_photo_and_filters(self):
        own = self.create()
        foreign = self.create(actor=self.other, motivo='SEGREDO de outro')
        self.client.force_login(self.user)
        response = self.client.get('/agenda/')
        self.assertEqual([booking.pk for booking in response.context['object_list']], [own.pk])
        self.assertNotContains(response, 'SEGREDO')
        self.assertEqual(self.client.get('/agenda/', {'q': 'SEGREDO'}).context['paginator'].count, 0)
        for suffix in ('', 'historico/', 'criador/foto/'):
            self.assertEqual(self.client.get(f'/agenda/{foreign.pk}/{suffix}').status_code, 404)
        api = APIClient()
        api.force_login(self.user)
        self.assertEqual(api.get('/api/v1/agendamentos/').data['count'], 1)
        self.assertEqual(api.get(f'/api/v1/agendamentos/{own.pk}/').status_code, 200)
        for suffix in ('', 'historico/'):
            self.assertEqual(api.get(f'/api/v1/agendamentos/{foreign.pk}/{suffix}').status_code, 404)

    def test_pending_and_rejected_outside_current_month_are_visible_and_filterable(self):
        pending = self.create()
        rejected = self.create(actor=self.user, inicio=self.data['inicio'] - timedelta(days=70),
                               fim=self.data['fim'] - timedelta(days=70))
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
        url = f'/agenda/{booking.pk}/avaliar/'
        self.assertEqual(self.client.post(url, {'versao': 1, 'decisao': 'aprovar'}).status_code, 403)
        for suffix in ('editar/', 'cancelar/'):
            self.assertEqual(self.client.get(f'/agenda/{booking.pk}/{suffix}').status_code, 403)
        self.client.force_login(self.admin)
        response = self.client.get('/agenda/solicitacoes/')
        self.assertEqual([b.pk for b in response.context['object_list']], [booking.pk])
        self.assertContains(response, url)
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertRedirects(self.client.post(url, {'versao': 1, 'decisao': 'aprovar'}), '/agenda/solicitacoes/')
        self.assertContains(self.client.get(f'/agenda/{booking.pk}/'), 'Confirmado')
        self.assertEqual(self.client.post(url, {'versao': 1, 'decisao': 'rejeitar'}).status_code, 409)
        self.assertEqual(self.client.get('/agenda/solicitacoes/').context['paginator'].count, 0)

    def test_review_error_preserves_request_and_csrf_and_unknown_fields_are_rejected(self):
        booking = self.create()
        self.create(actor=self.admin)
        url = f'/agenda/{booking.pk}/avaliar/'
        self.client.force_login(self.admin)
        self.assertEqual(self.client.post(url, {'versao': 1, 'decisao': 'aprovar'}).status_code, 409)
        self.assertEqual(self.client.post(url, {'versao': 1, 'decisao': 'rejeitar', 'criado_por': self.admin.pk}).status_code, 400)
        secure = Client(enforce_csrf_checks=True)
        secure.force_login(self.admin)
        self.assertEqual(secure.post(url, {'versao': 1, 'decisao': 'rejeitar'}).status_code, 403)
        self.assertRedirects(self.client.post(url, {'versao': 1, 'decisao': 'rejeitar'}), '/agenda/solicitacoes/')
        self.client.force_login(self.user)
        self.assertContains(self.client.get('/agenda/'), 'Rejeitado')

    def test_forged_space_submission_is_rejected_for_both_roles(self):
        space_id = 42
        for actor in (self.admin, self.user):
            self.client.force_login(actor)
            response = self.client.get('/agenda/novo/')
            self.assertNotContains(response, '<option value="espaco"')
            data = self.web_data(categoria='espaco', objeto=space_id)
            data.pop('material_proprio')
            response = self.client.post('/agenda/novo/', data)
            self.assertEqual(response.status_code, 200)
            self.assertIn('categoria', response.context['form'].errors)
        self.assertFalse(Agendamento.objects.exists())

    def test_api_normal_creation_cannot_spoof_state_owner_or_manage_booking(self):
        api = APIClient()
        api.force_login(self.user)
        response = api.post('/api/v1/agendamentos/', self.data, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual((response.data['situacao'], response.data['criado_por']), ('pendente', self.user.pk))
        url = f'/api/v1/agendamentos/{response.data["id"]}/'
        for method in (api.patch, api.put, api.delete):
            self.assertEqual(method(url, {'versao': 1}, format='json').status_code, 403)
        for field in ('situacao', 'avaliado_por', 'avaliado_em', 'criado_por'):
            self.assertEqual(api.post('/api/v1/agendamentos/', {**self.data, field: 'confirmado'}, format='json').status_code, 400)
        space_id = 42
        self.assertEqual(api.post('/api/v1/agendamentos/', {**self.data, 'categoria': 'espaco',
            'objeto': space_id, 'material_proprio': None}, format='json').status_code, 400)

    def test_navigation_is_role_scoped_and_only_review_entry_is_current(self):
        self.client.force_login(self.user)
        response = self.client.get('/agenda/')
        self.assertContains(response, '/agenda/')
        self.assertNotContains(response, '/agenda/solicitacoes/')
        self.client.force_login(self.admin)
        response = self.client.get('/agenda/solicitacoes/')
        selected = [item['label'] for item in response.context['nav_items'] if item['current']]
        self.assertEqual(selected, ['Solicitações de agendamento'])

    def test_admin_request_filters_include_decisions_but_not_direct_admin_reservations(self):
        request = self.create()
        self.review(request)
        self.create(actor=self.admin, inicio=self.data['fim'], fim=self.data['fim'] + timedelta(hours=1))
        self.client.force_login(self.admin)
        response = self.client.get('/agenda/solicitacoes/', {'situacao': '', 'mes': ''})
        self.assertEqual([b.pk for b in response.context['object_list']], [request.pk])

    def test_decision_pages_remain_readable_after_evaluator_account_is_deleted(self):
        booking = self.create()
        self.review(booking)
        self.admin.delete()
        self.client.force_login(self.user)
        self.assertContains(self.client.get(f'/agenda/{booking.pk}/'), 'Conta removida')

    def test_dashboard_counts_only_own_confirmed_bookings(self):
        from core.dashboard import dashboard_context

        confirmed = self.create()
        self.review(confirmed)
        self.create(actor=self.other, inicio=self.data['fim'], fim=self.data['fim'] + timedelta(hours=1))
        self.create(inicio=self.data['fim'], fim=self.data['fim'] + timedelta(hours=1))
        context = dashboard_context(self.user, now=self.data['inicio'])
        days = [day for month in context['months'] for week in month['weeks'] for day in week if day['in_month']]
        self.assertEqual(sum(day['reservations'] for day in days), 1)

    def test_api_status_filters_and_pagination_never_include_other_users(self):
        for index in range(27):
            self.create(actor=self.user, motivo=f'Próprio {index}')
            self.create(actor=self.other, motivo='SEGREDO')
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
            url = f'/agenda/{booking.pk}/criador/foto/'
            self.client.force_login(self.user)
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertIn('no-store', response['Cache-Control'])
            response.close()
            self.client.force_login(self.other)
            self.assertEqual(self.client.get(url).status_code, 404)

    def test_admin_can_read_request_after_creator_account_is_deleted(self):
        booking = self.create()
        self.user.delete()
        self.client.force_login(self.admin)
        self.assertContains(self.client.get('/agenda/solicitacoes/'), 'Conta removida')
        self.assertEqual(self.client.get(f'/agenda/{booking.pk}/').status_code, 200)
