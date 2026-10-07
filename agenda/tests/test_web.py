from datetime import datetime

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client, TestCase

from agenda.models import AgendaEquipamento, BOOKING_MODELS, AgendaServico
from agenda.services import cancel_booking, save_booking
from catalogo.models import Equipamento, Servico


class BookingWebTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_user('gestor')
        cls.admin.groups.add(Group.objects.get(name='Administradores'))
        cls.user = get_user_model().objects.create_user('comum', is_staff=True)
        cls.service = Servico.objects.first()
        cls.equipment = Equipamento.objects.create(nome='Impressora')

    def setUp(self):
        self.client.force_login(self.admin)
        self.data = {'categoria': 'servico', 'objeto': self.service.pk, 'motivo': 'Protótipo',
                     'dia': '2026-11-01', 'hora_inicio': '14:00:00', 'hora_termino': '15:00:00', 'material_proprio': 'sim'}

    def create(self, **overrides):
        data = {**self.data, **overrides}
        if data['categoria'] == 'servico':
            data['material_proprio'] = data['material_proprio'] == 'sim'
        else:
            data.pop('material_proprio', None)
        day, start, end = (data.pop(name) for name in ('dia', 'hora_inicio', 'hora_termino'))
        data['inicio'] = datetime.fromisoformat(data.get('inicio', f'{day}T{start}') + '-03:00')
        data['fim'] = datetime.fromisoformat(data.get('fim', f'{day}T{end}') + '-03:00')
        return save_booking(actor=self.admin, data=data)

    def test_login_redirect_and_normal_user_access_is_limited_by_owner_and_action(self):
        booking = self.create()
        urls = ['/agenda/', '/agenda/novo/', f'/agenda/{booking.categoria}/{booking.pk}/', f'/agenda/{booking.categoria}/{booking.pk}/editar/',
                f'/agenda/{booking.categoria}/{booking.pk}/cancelar/', f'/agenda/{booking.categoria}/{booking.pk}/historico/']
        self.client.logout()
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get('/agenda/').status_code, 200)
        self.assertEqual(self.client.get('/agenda/novo/').status_code, 200)
        for suffix in ('', 'historico/'):
            self.assertEqual(self.client.get(f'/agenda/{booking.categoria}/{booking.pk}/{suffix}').status_code, 404)
        for suffix in ('editar/', 'cancelar/'):
            self.assertEqual(self.client.get(f'/agenda/{booking.categoria}/{booking.pk}/{suffix}').status_code, 403)
        self.assertEqual(self.client.post('/agenda/novo/', self.data).status_code, 302)

    def test_admin_can_create_each_category_edit_view_history_and_cancel(self):
        for category, target in (('servico', self.service), ('equipamento', self.equipment)):
            category_data = {**self.data, 'categoria': category, 'objeto': target.pk}
            if category != 'servico':
                category_data.pop('material_proprio')
            response = self.client.post('/agenda/novo/', category_data)
            booking = BOOKING_MODELS[category].objects.get(**{category + '_id': target.pk})
            self.assertRedirects(response, f'/agenda/{booking.categoria}/{booking.pk}/')
            self.assertContains(self.client.get(response.url), target.nome)
            response = self.client.post(f'/agenda/{booking.categoria}/{booking.pk}/editar/', {**category_data, 'categoria': category,
                                        'objeto': target.pk, 'versao': 1, 'motivo': 'Corrigido'})
            self.assertRedirects(response, f'/agenda/{booking.categoria}/{booking.pk}/')
            self.assertContains(self.client.get(f'/agenda/{booking.categoria}/{booking.pk}/historico/'), 'Corrigido')
            self.assertContains(self.client.get(f'/agenda/{booking.categoria}/{booking.pk}/cancelar/'), 'Confirmar cancelamento')
            self.assertRedirects(self.client.post(f'/agenda/{booking.categoria}/{booking.pk}/cancelar/', {'versao': 2}), '/agenda/')
            self.assertEqual(self.client.get(f'/agenda/{booking.categoria}/{booking.pk}/').status_code, 404)
            self.assertEqual(type(booking).objects.get(pk=booking.pk).eventos.count(), 3)

    def test_form_options_follow_selected_category_and_reject_foreign_or_disabled_target(self):
        response = self.client.get('/agenda/novo/', {'categoria': 'equipamento'})
        self.assertQuerySetEqual(response.context['form'].fields['objeto'].queryset,
                                 Equipamento.objects.exclude(status='indisponivel').order_by('nome', 'pk'))
        self.equipment.status = 'indisponivel'
        self.equipment.save()
        response = self.client.post('/agenda/novo/', {**self.data, 'categoria': 'equipamento', 'objeto': self.equipment.pk})
        self.assertContains(response, 'Faça uma escolha válida')

    def test_refresh_options_preserves_unsaved_fields_without_validation_or_writing(self):
        response = self.client.post('/agenda/novo/', {'categoria': 'equipamento',
                                   'motivo': 'Texto ainda em edição', 'atualizar': '1'})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['form'].errors)
        self.assertContains(response, 'Texto ainda em edição')
        self.assertQuerySetEqual(response.context['form'].fields['objeto'].queryset,
                                 Equipamento.objects.exclude(status='indisponivel').order_by('nome', 'pk'))
        self.assertFalse(AgendaServico.objects.exists())
        response = self.client.post('/agenda/novo/', {**self.data, 'categoria': 'equipamento', 'objeto': 999999})
        self.assertEqual((AgendaServico.objects.count() + AgendaEquipamento.objects.count()), 0)
        self.assertContains(response, 'Faça uma escolha válida')

    def test_overlap_and_stale_edit_or_cancellation_show_409(self):
        booking = self.create()
        self.assertContains(self.client.post('/agenda/novo/', self.data), 'Já existe uma reserva', status_code=409)
        save_booking(actor=self.admin, category=booking.categoria, booking_id=booking.pk, expected_version=1, data={'motivo': 'Atualizado'})
        self.assertContains(self.client.post(f'/agenda/{booking.categoria}/{booking.pk}/editar/', {**self.data, 'versao': 1}),
                            'O agendamento foi alterado', status_code=409)
        self.assertContains(self.client.post(f'/agenda/{booking.categoria}/{booking.pk}/cancelar/', {'versao': 1}),
                            'O agendamento foi alterado', status_code=409)
        booking.refresh_from_db()
        self.assertEqual((booking.motivo, booking.versao), ('Atualizado', 2))

    def test_unchanged_web_dates_preserve_api_seconds_and_fractional_precision(self):
        booking = self.create(inicio='2026-11-01T14:00:37.123456', fim='2026-11-01T15:00:41.654321')
        response = self.client.get(f'/agenda/{booking.categoria}/{booking.pk}/editar/')
        self.assertContains(response, 'value="14:00:37"')
        response = self.client.post(f'/agenda/{booking.categoria}/{booking.pk}/editar/', {**self.data, 'versao': 1,
                                   'hora_inicio': '14:00:37', 'hora_termino': '15:00:41', 'motivo': 'Editado'})
        self.assertEqual(response.status_code, 302)
        booking.refresh_from_db()
        self.assertEqual((booking.inicio.microsecond, booking.fim.microsecond), (123456, 654321))
        self.assertEqual(set(booking.eventos.get(acao='editar').alteracoes), {'motivo'})

    def test_refresh_options_keeps_stale_version_and_cannot_overwrite_other_session(self):
        booking = self.create()
        other_client = Client()
        other_client.force_login(self.admin)
        url = f'/agenda/{booking.categoria}/{booking.pk}/editar/'
        self.assertEqual(other_client.post(url, {**self.data, 'versao': 1, 'motivo': 'Outra sessão'}).status_code, 302)
        response = self.client.post(url, {**self.data, 'versao': 1, 'motivo': 'Rascunho antigo', 'atualizar': '1'})
        refreshed_version = response.context['form']['versao'].value()
        self.assertEqual(str(refreshed_version), '1')
        response = self.client.post(url, {**self.data, 'versao': refreshed_version, 'motivo': 'Rascunho antigo'})
        self.assertEqual(response.status_code, 409)
        booking.refresh_from_db()
        self.assertEqual((booking.motivo, booking.versao, booking.eventos.count()), ('Outra sessão', 2, 2))

    def test_refresh_options_never_supplies_missing_or_invalid_edit_version(self):
        booking = self.create()
        url = f'/agenda/{booking.categoria}/{booking.pk}/editar/'
        for value in ('', 'inválida'):
            response = self.client.post(url, {**self.data, 'atualizar': '1', 'versao': value})
            self.assertEqual(response.context['form']['versao'].value(), value)

    def test_month_calendar_counts_cross_midnight_and_all_pages_with_half_open_intervals(self):
        self.create(inicio='2026-10-31T23:00:00', fim='2026-11-01T01:00:00')
        self.create(inicio='2026-11-01T02:00:00', fim='2026-11-02T00:00:00')
        for index in range(25):
            target = Servico.objects.create(nome=f'Serviço {index}')
            self.create(objeto=target.pk)
        response = self.client.get('/agenda/', {'mes': '2026-11'})
        self.assertEqual((response.context['paginator'].count, len(response.context['object_list'])), (27, 25))
        days = {day['date'].day: day['count'] for week in response.context['weeks'] for day in week if day['in_month']}
        self.assertEqual((days[1], days[2]), (27, 0))
        self.assertContains(response, 'Próxima')
        self.assertEqual(len(self.client.get('/agenda/', {'mes': '2026-11', 'page': 2}).context['object_list']), 2)

    def test_category_filter_and_invalid_filters(self):
        self.create()
        self.create(categoria='equipamento', objeto=self.equipment.pk)
        response = self.client.get('/agenda/', {'mes': '2026-11', 'categoria': 'equipamento'})
        self.assertEqual(response.context['paginator'].count, 1)
        for fields in ({'mes': '2026-13'}, {'categoria': 'outro'}):
            self.assertEqual(self.client.get('/agenda/', fields).status_code, 400)

    def test_unknown_fields_missing_version_and_get_cancellation_do_not_change_data(self):
        booking = self.create()
        self.client.get(f'/agenda/{booking.categoria}/{booking.pk}/cancelar/')
        for fields in ({'cancelado_em': '2026-11-01'}, {'versao': ''}):
            response = self.client.post(f'/agenda/{booking.categoria}/{booking.pk}/editar/', {**self.data, 'versao': 1, **fields})
            self.assertEqual(response.status_code, 200)
        booking.refresh_from_db()
        self.assertEqual((booking.versao, booking.cancelado_em, booking.eventos.count()), (1, None, 1))

    def test_csrf_required_and_cancellation_releases_calendar_slot(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.admin)
        self.assertEqual(client.post('/agenda/novo/', self.data).status_code, 403)
        booking = self.create()
        cancel_booking(actor=self.admin, category=booking.categoria, booking_id=booking.pk, expected_version=1)
        response = self.client.get('/agenda/', {'mes': '2026-11'})
        self.assertEqual(response.context['paginator'].count, 0)
        self.assertRedirects(self.client.post('/agenda/novo/', self.data), f'/agenda/servico/{AgendaServico.objects.latest("pk").pk}/')
