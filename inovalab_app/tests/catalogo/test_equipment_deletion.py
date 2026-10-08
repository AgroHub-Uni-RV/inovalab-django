from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.test import Client, TestCase
from django.core.management import call_command
from io import StringIO
from rest_framework.test import APIClient
from inovalab_app.catalogo.models import Equipamento
from inovalab_app.catalogo import services


class EquipmentDeletionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_superuser('infra-admin')
        cls.reader = get_user_model().objects.create_user('infra-leitor', is_staff=True)

    def test_deleted_seed_does_not_reappear_or_lose_photo(self):
        equipment = Equipamento.objects.first()
        photo = equipment.foto.name
        services.delete_equipment(actor=self.admin, equipment_id=equipment.pk)
        call_command('seed_inovalab', stdout=StringIO())
        equipment.refresh_from_db()
        self.assertIsNotNone(equipment.excluido_em)
        self.assertEqual(equipment.foto.name, photo)
        self.client.force_login(self.admin)
        self.assertNotContains(self.client.get('/catalogo/equipamentos/'), f'/equipamentos/{equipment.pk}/')

    def test_get_is_only_confirmation_and_post_requires_admin_and_csrf(self):
        equipment = Equipamento.objects.first()
        url = f'/catalogo/equipamentos/{equipment.pk}/excluir/'
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.admin)
        self.assertEqual(client.get(url).status_code, 200)
        equipment.refresh_from_db()
        self.assertIsNone(equipment.excluido_em)
        self.assertEqual(client.post(url).status_code, 403)
        client.force_login(self.reader)
        self.assertEqual(client.get(url).status_code, 403)
        with self.assertRaises(PermissionDenied):
            services.delete_equipment(actor=self.reader, equipment_id=equipment.pk)

    def test_api_delete_preserves_row_and_blocks_editing_deleted_equipment(self):
        equipment = Equipamento.objects.first()
        api = APIClient()
        api.force_login(self.admin)
        url = f'/api/v1/equipamentos/{equipment.pk}/'
        self.assertEqual(api.delete(url).status_code, 204)
        equipment.refresh_from_db()
        self.assertIsNotNone(equipment.excluido_em)
        self.assertEqual(api.patch(url, {'nome': 'Recuperado'}, format='json').status_code, 404)
