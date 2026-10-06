from datetime import datetime

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from agenda.forms import BookingForm
from agenda.models import Agendamento
from agenda.services import save_booking
from catalogo.models import Espaco


class BookingIdentityScheduleTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user('ana', first_name='Ana', last_name='Silva')
        cls.admin = get_user_model().objects.create_superuser('gestor')
        cls.space = Espaco.objects.create(nome='Sala de teste')

    def setUp(self):
        self.client.force_login(self.user)
        self.web = dict(categoria='espaco', objeto=self.space.pk, motivo='Projeto',
                        dia='2026-11-01', hora_inicio='14:00:00', hora_termino='15:00:00')
        self.data = dict(categoria='espaco', objeto=self.space.pk, motivo='Projeto',
                         inicio=datetime.fromisoformat('2026-11-01T14:00:00-03:00'),
                         fim=datetime.fromisoformat('2026-11-01T15:00:00-03:00'))

    def test_web_creates_booking_for_authenticated_user_with_local_day_and_hours(self):
        response = self.client.post('/agenda/novo/', self.web)
        self.assertEqual(response.status_code, 302)
        booking = Agendamento.objects.get()
        self.assertEqual((booking.criado_por_id, booking.situacao), (self.user.pk, 'pendente'))
        self.assertEqual(booking.inicio, self.data['inicio'])
        self.assertEqual(booking.fim, self.data['fim'])
        self.assertContains(self.client.get(response.url), 'Ana Silva')

    def test_new_form_uses_one_date_and_two_time_inputs(self):
        response = self.client.get('/agenda/novo/?categoria=espaco')
        self.assertContains(response, 'type="date" name="dia"')
        self.assertContains(response, 'type="time" name="hora_inicio"')
        self.assertContains(response, 'type="time" name="hora_termino"')
        self.assertNotContains(response, 'name="requerente"')
        self.assertNotContains(response, 'datetime-local')

    def test_end_at_or_before_start_does_not_create_booking(self):
        for end in ('14:00:00', '13:00:00'):
            response = self.client.post('/agenda/novo/', {**self.web, 'hora_termino': end})
            self.assertEqual(response.status_code, 200)
            self.assertIn('hora_termino', response.context['form'].errors)
        self.assertFalse(Agendamento.objects.exists())

    def test_refresh_keeps_day_and_hours_without_writing(self):
        response = self.client.post('/agenda/novo/', {**self.web, 'atualizar': '1'})
        form = response.context['form']
        self.assertEqual(form['dia'].value(), '2026-11-01')
        self.assertEqual(form['hora_inicio'].value(), '14:00:00')
        self.assertEqual(form['hora_termino'].value(), '15:00:00')
        self.assertFalse(Agendamento.objects.exists())

    def test_admin_edit_does_not_replace_creator(self):
        booking = save_booking(actor=self.user, data=self.data)
        self.client.force_login(self.admin)
        response = self.client.post(f'/agenda/{booking.pk}/editar/',
                                    {**self.web, 'versao': 1, 'motivo': 'Correção'})
        self.assertEqual(response.status_code, 302)
        booking.refresh_from_db()
        self.assertEqual(booking.criado_por_id, self.user.pk)
        self.assertEqual(booking.eventos.first().ator_id, self.admin.pk)

    def test_api_derives_creator_and_rejects_identity_spoofing(self):
        api = APIClient()
        api.force_login(self.user)
        response = api.post('/api/v1/agendamentos/', self.data, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['criado_por'], self.user.pk)
        self.assertNotIn('requerente', response.data)
        for field, value in [('requerente', 'Outra pessoa'), ('criado_por', self.admin.pk)]:
            response = api.post('/api/v1/agendamentos/', {**self.data, field: value}, format='json')
            self.assertEqual(response.status_code, 400)
        self.assertEqual(Agendamento.objects.count(), 1)

    def test_service_rejects_free_requester(self):
        with self.assertRaises(ValidationError):
            save_booking(actor=self.user, data={**self.data, 'requerente': 'Outra pessoa'})
        self.assertFalse(Agendamento.objects.exists())

    def test_unchanged_legacy_multiday_period_is_not_silently_shortened(self):
        booking = save_booking(actor=self.user, data={**self.data,
                               'fim': datetime.fromisoformat('2026-11-03T15:00:00-03:00')})
        self.client.force_login(self.admin)
        response = self.client.post(f'/agenda/{booking.pk}/editar/',
                                    {**self.web, 'versao': 1, 'motivo': 'Correção'})
        self.assertEqual(response.status_code, 302)
        booking.refresh_from_db()
        self.assertEqual(timezone.localtime(booking.fim).isoformat(), '2026-11-03T15:00:00-03:00')
        self.assertEqual(set(booking.eventos.first().alteracoes), {'motivo'})

    def test_edit_initial_uses_brasilia_day_for_utc_timestamp(self):
        booking = save_booking(actor=self.user, data={**self.data,
            'inicio': datetime.fromisoformat('2026-11-02T01:00:00+00:00'),
            'fim': datetime.fromisoformat('2026-11-02T02:00:00+00:00')})
        form = BookingForm(booking=booking, actor=self.admin)
        self.assertEqual(str(form.initial['dia']), '2026-11-01')
        self.assertEqual(str(form.initial['hora_inicio']), '22:00:00')
        self.assertEqual(str(form.initial['hora_termino']), '23:00:00')

    def test_search_finds_creator_login_first_name_and_last_name(self):
        booking = save_booking(actor=self.user, data=self.data)
        self.client.force_login(self.admin)
        for query in ('ana', 'Silva', 'Ana Silva'):
            response = self.client.get('/agenda/', {'q': query, 'mes': ''})
            self.assertEqual([item.pk for item in response.context['object_list']], [booking.pk])

    def test_changed_legacy_period_uses_only_selected_day(self):
        booking = save_booking(actor=self.user, data={**self.data,
                               'fim': datetime.fromisoformat('2026-11-03T15:00:00-03:00')})
        self.client.force_login(self.admin)
        response = self.client.post(f'/agenda/{booking.pk}/editar/',
                                    {**self.web, 'dia': '2026-11-05', 'versao': 1})
        self.assertEqual(response.status_code, 302)
        booking.refresh_from_db()
        self.assertEqual(timezone.localtime(booking.inicio).isoformat(), '2026-11-05T14:00:00-03:00')
        self.assertEqual(timezone.localtime(booking.fim).isoformat(), '2026-11-05T15:00:00-03:00')

    def test_metadata_edit_preserves_valid_subsecond_interval(self):
        booking = save_booking(actor=self.user, data={**self.data,
            'inicio': datetime.fromisoformat('2026-11-01T14:00:00.100000-03:00'),
            'fim': datetime.fromisoformat('2026-11-01T14:00:00.900000-03:00')})
        self.client.force_login(self.admin)
        response = self.client.post(f'/agenda/{booking.pk}/editar/',
            {**self.web, 'hora_termino': '14:00:00', 'versao': 1, 'motivo': 'Correção'})
        self.assertEqual(response.status_code, 302)
        booking.refresh_from_db()
        self.assertEqual((booking.inicio.microsecond, booking.fim.microsecond), (100000, 900000))
        self.assertEqual(set(booking.eventos.first().alteracoes), {'motivo'})

    def test_unsaved_booking_has_printable_identity_without_history(self):
        booking = Agendamento(espaco=self.space, motivo='Projeto')
        self.assertEqual(str(booking), 'Sala de teste — Não registrado')
