from datetime import datetime, timedelta
from decimal import Decimal
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from agenda.forms import BookingForm
from agenda.models import AgendaEquipamento, BOOKING_MODELS, AgendaServico, EventoAgendamento
from agenda.services import BookingConflict, cancel_booking, save_booking
from catalogo.models import Equipamento, Servico
from conteudo.tests.helpers import image_upload
from materiais.models import Material


class BookingServiceDetailsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_user('criador', first_name='Nicole', last_name='Dias')
        cls.admin.groups.add(Group.objects.get(name='Administradores'))
        cls.editor = get_user_model().objects.create_user('editor')
        cls.editor.groups.add(Group.objects.get(name='Administradores'))
        cls.reader = get_user_model().objects.create_user('leitor', is_staff=True)
        cls.service = Servico.objects.first()
        cls.machine = Equipamento.objects.create(nome='Máquina A')
        cls.other_machine = Equipamento.objects.create(nome='Máquina B')
        cls.material = Material.objects.create(nome='PLA', categoria='Filamento', quantidade=500,
                                              unidade='g', fonte='Laboratório')

    def setUp(self):
        self.client.force_login(self.admin)
        self.data = {'categoria': 'servico', 'objeto': self.service.pk,
                     'motivo': 'Produção', 'inicio': datetime.fromisoformat('2026-11-01T10:00:00-03:00'),
                     'fim': datetime.fromisoformat('2026-11-01T11:00:00-03:00')}

    def create(self, **overrides):
        return save_booking(actor=self.admin, data={**self.data, **overrides})

    def web_data(self, **overrides):
        data = {key: value for key, value in self.data.items() if key not in ('inicio', 'fim')}
        return {**data, 'dia': '2026-11-01', 'hora_inicio': '10:00:00', 'hora_termino': '11:00:00',
                'material_proprio': 'sim', **overrides}

    def test_multiple_equipment_and_lab_material_are_saved_and_recorded(self):
        booking = self.create(equipamentos=[self.machine.pk, self.other_machine.pk], material_proprio=False,
                              material_gasto_gramas=Decimal('25.125'))
        booking.refresh_from_db()
        self.assertEqual(set(booking.equipamentos.values_list('pk', flat=True)), {self.machine.pk, self.other_machine.pk})
        self.assertEqual(booking.material_gasto_gramas, Decimal('25.125'))
        event = booking.eventos.get()
        self.assertEqual(event.alteracoes['material_gasto_gramas']['novo'], '25.125')
        self.assertEqual(event.alteracoes['equipamentos']['novo'], [self.machine.pk, self.other_machine.pk])

    def test_service_can_use_own_material_without_equipment_or_spending(self):
        booking = self.create(material_proprio=True)
        self.assertFalse(booking.equipamentos.exists())
        self.assertIsNone(booking.material_gasto_gramas)

    def test_lab_material_requires_positive_grams_and_at_most_three_decimal_places(self):
        for amount in (None, 0, -1, Decimal('0.0001'), Decimal('1000000000'), 'inválido'):
            with self.subTest(amount=amount), self.assertRaises(ValidationError):
                self.create(material_proprio=False, material_gasto_gramas=amount)
        self.assertFalse(AgendaServico.objects.exists())
        self.assertFalse(EventoAgendamento.objects.exists())

    def test_wrong_category_and_inconsistent_material_are_rejected(self):
        for fields in ({'material_proprio': True, 'material_gasto_gramas': 10},
                       {'material_gasto_gramas': 10}, {'material_proprio': 'false'},
                       {'categoria': 'espaco', 'objeto': 42, 'material_proprio': True},
                       {'categoria': 'equipamento', 'objeto': self.machine.pk, 'equipamentos': [self.other_machine.pk]}):
            with self.subTest(fields=fields), self.assertRaises(ValidationError):
                self.create(**fields)
        self.assertFalse(AgendaServico.objects.exists())

    def test_invalid_missing_and_unavailable_equipment_do_not_persist(self):
        self.machine.status = 'indisponivel'
        self.machine.save()
        for equipment in ([self.machine.pk], [999999], [True], ['1'], [self.other_machine.pk]*2):
            with self.subTest(equipment=equipment), self.assertRaises(ValidationError):
                self.create(equipamentos=equipment)
        self.assertFalse(AgendaServico.objects.exists())

    def test_existing_unavailable_equipment_can_be_retained_for_metadata_edit(self):
        booking = self.create(equipamentos=[self.machine.pk], material_proprio=False, material_gasto_gramas=25)
        self.machine.status = 'indisponivel'
        self.machine.save()
        saved = save_booking(actor=self.editor, category=booking.categoria, booking_id=booking.pk, expected_version=1, data={'motivo': 'Correção'})
        self.assertEqual(saved.criado_por_id, self.admin.pk)
        self.assertEqual(saved.eventos.get(acao='editar').alteracoes, {'motivo': {'anterior': 'Produção', 'novo': 'Correção'}})
        self.assertIn(self.machine, BookingForm(booking=saved).fields['equipamentos'].queryset)
        with self.assertRaises(ValidationError):
            save_booking(actor=self.admin, category=booking.categoria, booking_id=booking.pk, expected_version=2,
                         data={'fim': self.data['fim']+timedelta(hours=1)})

    def test_category_change_is_rejected_preserving_service_details_and_history(self):
        booking = self.create(equipamentos=[self.machine.pk], material_proprio=False, material_gasto_gramas=12)
        with self.assertRaises(ValidationError):
            save_booking(actor=self.admin, category=booking.categoria, booking_id=booking.pk, expected_version=1,
                         data={'categoria': 'equipamento', 'objeto': self.machine.pk})
        booking.refresh_from_db()
        self.assertEqual(list(booking.equipamentos.values_list('pk', flat=True)), [self.machine.pk])
        self.assertEqual(booking.material_gasto_gramas, Decimal('12.000'))
        self.assertEqual(booking.eventos.count(), 1)
        self.assertEqual(booking.versao, 1)


    def test_cancel_preserves_service_details_and_stale_update_cannot_change_them(self):
        booking = self.create(equipamentos=[self.machine.pk], material_proprio=False, material_gasto_gramas=12)
        save_booking(actor=self.admin, category=booking.categoria, booking_id=booking.pk, expected_version=1, data={'motivo': 'Atualizado'})
        with self.assertRaises(BookingConflict):
            save_booking(actor=self.admin, category=booking.categoria, booking_id=booking.pk, expected_version=1,
                         data={'equipamentos': [self.other_machine.pk], 'material_gasto_gramas': 50})
        cancel_booking(actor=self.admin, category=booking.categoria, booking_id=booking.pk, expected_version=2)
        booking.refresh_from_db()
        self.assertEqual(list(booking.equipamentos.values_list('pk', flat=True)), [self.machine.pk])
        self.assertEqual(booking.material_gasto_gramas, Decimal('12.000'))
        self.assertEqual(booking.eventos.count(), 3)

    def test_associated_equipment_does_not_implicitly_reserve_machine(self):
        self.create(equipamentos=[self.machine.pk])
        machine_booking = self.create(categoria='equipamento', objeto=self.machine.pk)
        self.assertEqual(machine_booking.equipamento_id, self.machine.pk)
        self.assertEqual((AgendaServico.objects.count() + AgendaEquipamento.objects.count()), 2)

    def test_database_enforces_material_invariants_even_without_validation(self):
        base = {key: value for key, value in self.data.items() if key not in ('categoria', 'objeto')}
        for fields in ({'material_proprio': False}, {'material_proprio': False, 'material_gasto_gramas': 0},
                       {'material_proprio': True, 'material_gasto_gramas': 1}, {'material_gasto_gramas': 1}):
            with self.subTest(fields=fields), self.assertRaises(IntegrityError), transaction.atomic():
                AgendaServico.objects.create(servico=self.service, **base, **fields)

    def test_forms_are_specific_to_category_and_require_material_choice(self):
        service_form = self.client.get('/agenda/novo/?categoria=servico').context['form']
        self.assertIn('equipamentos', service_form.fields)
        self.assertFalse(service_form.fields['equipamentos'].required)
        for category in ('equipamento',):
            form = self.client.get('/agenda/novo/', {'categoria': category}).context['form']
            self.assertFalse({'equipamentos', 'material_proprio', 'material_gasto_gramas'} & set(form.fields))
        data = self.web_data()
        data.pop('material_proprio')
        response = self.client.post('/agenda/novo/', data)
        self.assertIn('material_proprio', response.context['form'].errors)
        response = self.client.post('/agenda/novo/', self.web_data(material_proprio='nao'))
        self.assertIn('material_gasto_gramas', response.context['form'].errors)
        self.assertFalse(AgendaServico.objects.exists())

    def test_web_submission_and_refresh_preserve_multiple_equipment_and_decimal_spending(self):
        data = self.web_data(equipamentos=[self.machine.pk, self.other_machine.pk],
                             material_proprio='nao', material_gasto=self.material.pk, material_gasto_gramas='12.125')
        refreshed = self.client.post('/agenda/novo/', {**data, 'atualizar': '1'})
        self.assertEqual(refreshed.context['form']['equipamentos'].value(), [str(self.machine.pk), str(self.other_machine.pk)])
        self.assertEqual(refreshed.context['form']['material_gasto_gramas'].value(), '12.125')
        self.assertFalse(AgendaServico.objects.exists())
        response = self.client.post('/agenda/novo/', data)
        booking = AgendaServico.objects.get()
        self.assertRedirects(response, f'/agenda/{booking.categoria}/{booking.pk}/')
        self.assertContains(self.client.get(response.url), '12,125 g')
        self.assertEqual(booking.equipamentos.count(), 2)

    def test_internal_api_supports_details_and_retains_existing_contract_without_new_fields(self):
        client = APIClient()
        client.force_login(self.admin)
        response = client.post('/api/v1/agendamentos/', {**self.data, 'equipamentos': [self.machine.pk],
            'material_proprio': False, 'material_gasto_gramas': '12.125'}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['equipamentos'], [self.machine.pk])
        self.assertEqual(response.data['material_gasto_gramas'], '12.125')
        url = f'/api/v1/agendamentos/{response.data["categoria"]}/{response.data["id"]}/'
        self.assertEqual(client.get(url).data['material_proprio'], False)
        updated = client.patch(url, {'versao': 1, 'material_proprio': True}, format='json')
        self.assertEqual(updated.status_code, 200, updated.data)
        self.assertIsNone(updated.data['material_gasto_gramas'])
        for fields in ({'versao': 2, 'material_proprio': False}, {'versao': 2, 'equipamentos': [True]}):
            self.assertEqual(client.patch(url, fields, format='json').status_code, 400)
        legacy = self.create(objeto=Servico.objects.create(nome='Outro serviço').pk)
        self.assertIsNone(legacy.material_proprio)

    def test_detail_header_shows_creator_name_instead_of_requester(self):
        booking = self.create(material_proprio=True)
        response = self.client.get(f'/agenda/{booking.categoria}/{booking.pk}/')
        self.assertEqual(response.context['creator_name'], 'Nicole Dias')
        self.assertContains(response, 'aria-label="Criado por Nicole Dias"')
        self.assertNotContains(response, '<dt>Requerente</dt>')
        self.assertContains(response, 'class="booking-category">Serviços')
        self.assertNotContains(response, 'aria-label="Criado por Requerente distinto"')

    def test_external_creator_falls_back_to_creation_history_name(self):
        booking = self.create()
        AgendaServico.objects.filter(pk=booking.pk).update(criado_por=None)
        booking.eventos.filter(acao='criar').update(ator_nome='Integração: AgroHub')
        response = self.client.get(f'/agenda/{booking.categoria}/{booking.pk}/')
        self.assertEqual(response.context['creator_name'], 'Integração: AgroHub')
        self.assertNotContains(response, '/criador/foto/')

    def test_creator_photo_is_available_only_to_authorized_agenda_users(self):
        with TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            self.admin.foto.save('criador.webp', image_upload(), save=True)
            booking = self.create()
            self.client.force_login(self.editor)
            url = f'/agenda/{booking.categoria}/{booking.pk}/criador/foto/'
            self.assertContains(self.client.get(f'/agenda/{booking.categoria}/{booking.pk}/'), url)
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response['Content-Type'], 'image/webp')
            self.assertIn('no-store', response['Cache-Control'])
            response.close()
            self.assertEqual(self.client.get(f'/usuarios/{self.admin.pk}/foto/').status_code, 403)
            self.client.force_login(self.reader)
            self.assertEqual(self.client.get(url).status_code, 404)
            self.client.logout()
            self.assertEqual(self.client.get(url).status_code, 302)
