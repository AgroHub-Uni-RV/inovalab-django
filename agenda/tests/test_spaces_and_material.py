from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework.test import APIClient

from agenda.forms import BookingForm
from agenda.models import Agendamento
from agenda.services import BookingConflict, cancel_booking, save_booking
from catalogo.models import Equipamento, Espaco, Servico
from materiais.models import Material


class SpacesAndMaterialTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_user('gestor_materiais')
        cls.admin.groups.add(Group.objects.get(name='Administradores'))
        cls.service = Servico.objects.first()
        cls.material = Material.objects.create(nome='PLA azul', categoria='Filamento', quantidade=500,
                                              unidade='g', fonte='Laboratório')
        cls.other = Material.objects.create(nome='ABS', categoria='Filamento', quantidade=200,
                                           unidade='kg', fonte='Laboratório', status='indisponivel')

    def setUp(self):
        self.client.force_login(self.admin)
        start = timezone.now() + timedelta(days=30)
        self.data = dict(categoria='servico', objeto=self.service.pk, motivo='Protótipo',
                         inicio=start, fim=start+timedelta(hours=1), material_proprio=False,
                         material_gasto=self.material.pk, material_gasto_gramas='12.125')

    def create(self, **overrides):
        return save_booking(actor=self.admin, data={**self.data, **overrides})

    def web_data(self, **overrides):
        data = {key: value for key, value in self.data.items() if key not in ('inicio', 'fim')}
        return {**data, 'material_proprio': 'nao', 'dia': '2026-12-01',
                'hora_inicio': '10:00:00', 'hora_termino': '11:00:00', **overrides}

    def test_web_requires_material_when_lab_supplies_it_and_shows_it_in_detail(self):
        response = self.client.post('/agenda/novo/', self.web_data(material_gasto=''))
        self.assertIn('material_gasto', response.context['form'].errors)
        self.assertFalse(Agendamento.objects.exists())
        response = self.client.post('/agenda/novo/', self.web_data())
        booking = Agendamento.objects.get()
        self.assertRedirects(response, f'/agenda/{booking.pk}/')
        self.assertEqual(booking.material_gasto_id, self.material.pk)
        self.assertContains(self.client.get(response.url), 'PLA azul')
        self.assertContains(self.client.get(response.url), '12,125 g')
        self.material.refresh_from_db()
        self.assertEqual(self.material.quantidade, 500)

    def test_web_material_selection_is_preserved_on_refresh_and_edit(self):
        response = self.client.post('/agenda/novo/', {**self.web_data(), 'atualizar': '1'})
        self.assertEqual(str(response.context['form']['material_gasto'].value()), str(self.material.pk))
        self.assertFalse(Agendamento.objects.exists())
        booking = self.create()
        self.assertEqual(BookingForm(booking=booking).initial['material_gasto'], self.material.pk)

    def test_material_cannot_be_invalid_unavailable_or_used_with_own_material(self):
        for changes in ({'material_gasto': True}, {'material_gasto': '1'}, {'material_gasto': 999999},
                        {'material_gasto': self.other.pk}, {'material_proprio': True, 'material_gasto_gramas': None},
                        {'material_proprio': None, 'material_gasto_gramas': None},
                        {'categoria': 'espaco', 'objeto': Espaco.objects.first().pk}):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                self.create(**changes)
        self.assertFalse(Agendamento.objects.exists())

    def test_unavailable_retained_material_allows_metadata_edit_but_not_new_period(self):
        booking = self.create()
        Material.objects.filter(pk=self.material.pk).update(status='indisponivel')
        form = BookingForm(booking=booking)
        self.assertIn(self.material, form.fields['material_gasto'].queryset)
        self.assertNotIn(self.other, form.fields['material_gasto'].queryset)
        save_booking(actor=self.admin, booking_id=booking.pk, expected_version=1, data={'motivo': 'Corrigido'})
        with self.assertRaises(ValidationError):
            save_booking(actor=self.admin, booking_id=booking.pk, expected_version=2,
                         data={'fim': self.data['fim']+timedelta(hours=1)})

    def test_history_and_own_material_change_clear_material_with_version_protection(self):
        booking = self.create()
        self.assertEqual(booking.eventos.get().alteracoes['material_gasto']['novo'], self.material.pk)
        saved = save_booking(actor=self.admin, booking_id=booking.pk, expected_version=1,
                             data={'material_proprio': True})
        self.assertIsNone(saved.material_gasto_id)
        self.assertIsNone(saved.material_gasto_gramas)
        self.assertEqual(saved.eventos.first().alteracoes['material_gasto'],
                         {'anterior': self.material.pk, 'novo': None})
        with self.assertRaises(BookingConflict):
            save_booking(actor=self.admin, booking_id=booking.pk, expected_version=1, data=self.data)

    def test_category_change_clears_material_and_cancel_retains_it(self):
        booking = self.create()
        cancel_booking(actor=self.admin, booking_id=booking.pk, expected_version=1)
        booking.refresh_from_db()
        self.assertEqual(booking.material_gasto_id, self.material.pk)
        other = self.create(inicio=self.data['inicio']+timedelta(days=1), fim=self.data['fim']+timedelta(days=1))
        updated = save_booking(actor=self.admin, booking_id=other.pk, expected_version=1,
                              data={'categoria': 'visita'})
        self.assertIsNone(updated.material_gasto_id)

    def test_api_material_id_roundtrip_and_legacy_spending_without_type(self):
        api = APIClient()
        api.force_login(self.admin)
        response = api.post('/api/v1/agendamentos/', self.data, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['material_gasto'], self.material.pk)
        url = f'/api/v1/agendamentos/{response.data["id"]}/'
        self.assertEqual(api.get(url).data['material_gasto'], self.material.pk)
        self.assertEqual(api.patch(url, {'versao': 1, 'material_gasto': True}, format='json').status_code, 400)
        legacy = self.create(material_gasto=None, inicio=self.data['inicio']+timedelta(days=2),
                             fim=self.data['fim']+timedelta(days=2))
        self.assertIsNone(legacy.material_gasto_id)

    def test_database_disallows_material_link_outside_lab_material_service(self):
        base = {key: value for key, value in self.data.items() if key not in ('categoria', 'objeto', 'material_gasto')}
        for flag in (None, True):
            with self.subTest(flag=flag), self.assertRaises(IntegrityError), transaction.atomic():
                Agendamento.objects.create(servico=self.service, material_gasto=self.material,
                                           **{**base, 'material_proprio': flag, 'material_gasto_gramas': None})

    def test_spaces_are_not_offered_in_new_booking_form(self):
        response = self.client.get('/agenda/novo/')
        self.assertNotContains(response, '<option value="espaco"')
        self.assertContains(response, '<option value="visita"')
        self.assertTrue(Espaco.objects.exists())

    def test_equipment_card_invalid_submission_preserves_selected_choice(self):
        equipment = Equipamento.objects.create(nome='Máquina de teste')
        data = {key: value for key, value in self.web_data().items() if not key.startswith('material_')}
        data.update(categoria='equipamento', objeto=equipment.pk)
        invalid = self.client.post('/agenda/novo/', {**data, 'motivo': ''})
        self.assertContains(invalid, f'value="{equipment.pk}" required id=')
        self.assertContains(invalid, 'checked')
        response = self.client.post('/agenda/novo/', data)
        booking = Agendamento.objects.get()
        self.assertRedirects(response, f'/agenda/{booking.pk}/')
        self.assertEqual(booking.equipamento_id, equipment.pk)
