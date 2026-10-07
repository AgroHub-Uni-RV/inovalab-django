from datetime import datetime
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from agenda.models import AgendaEquipamento, AgendaServico, EventoAgendamento
from catalogo.models import Equipamento, Servico


class BookingCreationFlowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_superuser('criacao-agenda')
        cls.service = Servico.objects.first()
        cls.equipment = Equipamento.objects.create(nome='Equipamento do fluxo')

    def setUp(self):
        self.client.force_login(self.admin)

    def test_entry_requires_choice_before_showing_a_form(self):
        with patch('agenda.views.BookingForm') as form:
            response = self.client.get('/agenda/novo/')
        self.assertTemplateUsed(response, 'agenda/choose_category.html')
        self.assertContains(response, 'class="booking-type-card"', count=3)
        for url in ('/agenda/visitas/novo/', '/agenda/novo/?categoria=equipamento',
                    '/agenda/novo/?categoria=servico'):
            self.assertContains(response, url)
        self.assertNotContains(response, 'class="sheet-form"')
        self.assertNotContains(response, 'name="objeto"')
        form.assert_not_called()
        self.assertFalse(EventoAgendamento.objects.exists())

    def test_unknown_category_returns_to_choice_without_defaulting_to_service(self):
        for category in ('espaco', 'invalida'):
            with self.subTest(category=category):
                response = self.client.get('/agenda/novo/', {'categoria': category})
                self.assertContains(response, 'Selecione uma das formas', status_code=400)
                self.assertTemplateUsed(response, 'agenda/choose_category.html')
                self.assertNotContains(response, 'name="objeto"', status_code=400)

    def test_selected_forms_only_offer_fields_for_the_chosen_category(self):
        for category in ('servico', 'equipamento'):
            with self.subTest(category=category):
                response = self.client.get('/agenda/novo/', {'categoria': category})
                self.assertEqual(response.context['form'].category, category)
                self.assertContains(response, f'type="hidden" name="categoria" value="{category}"')
                self.assertNotContains(response, '<select name="categoria"')
                self.assertNotContains(response, 'name="sala"')
                self.assertContains(response, 'Alterar tipo de agendamento')
                self.assertContains(response, 'Confirmar agendamento')
                if category == 'servico':
                    self.assertContains(response, 'name="material_proprio"')
                else:
                    self.assertNotContains(response, 'name="material_proprio"')

    def test_confirmation_validates_before_saving_only_the_selected_local_agenda(self):
        for category, target, model, other in (
            ('servico', self.service, AgendaServico, AgendaEquipamento),
            ('equipamento', self.equipment, AgendaEquipamento, AgendaServico),
        ):
            with self.subTest(category=category):
                url = f'/agenda/novo/?categoria={category}'
                payload = {'categoria': category, 'objeto': target.pk, 'motivo': 'Pedido do fluxo',
                           'dia': '2099-11-01', 'hora_inicio': '10:00', 'hora_termino': '11:00'}
                if category == 'servico':
                    payload['material_proprio'] = 'sim'
                self.client.get(url)
                other_count = other.objects.count()
                invalid = self.client.post(url, {**payload, 'hora_termino': '09:00'})
                self.assertIn('hora_termino', invalid.context['form'].errors)
                self.assertEqual(invalid.context['form']['categoria'].value(), category)
                self.assertEqual(invalid.context['form']['motivo'].value(), payload['motivo'])
                self.assertFalse(model.objects.exists())
                response = self.client.post(url, payload)
                booking = model.objects.get()
                self.assertRedirects(response, booking.get_absolute_url())
                self.assertEqual(booking.eventos.get().acao, 'criar')
                self.assertEqual(other.objects.count(), other_count)

    def test_edit_uses_existing_category_even_when_query_requests_another_type(self):
        booking = AgendaEquipamento.objects.create(
            equipamento=self.equipment, criado_por=self.admin, motivo='Agendamento existente',
            inicio=datetime.fromisoformat('2099-11-01T10:00:00-03:00'),
            fim=datetime.fromisoformat('2099-11-01T11:00:00-03:00'),
        )
        for category in ('servico', 'visita'):
            with self.subTest(category=category):
                response = self.client.get(booking.get_absolute_url() + 'editar/', {'categoria': category})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.context['form'].category, 'equipamento')
                self.assertContains(response, 'Editar agendamento')
                self.assertNotContains(response, 'name="material_proprio"')
