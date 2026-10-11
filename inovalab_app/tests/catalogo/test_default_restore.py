from io import BytesIO, StringIO
from tempfile import TemporaryDirectory

from PIL import Image
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from inovalab_app.catalogo.models import Equipamento
from inovalab_app.catalogo.services import delete_equipment, restore_default_equipment, save_entry
from inovalab_app.tests.conteudo.helpers import image_upload
from inovalab_app.tests.http import close_response


class DefaultEquipmentTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_superuser('padroes-admin')
        cls.reader = get_user_model().objects.create_user('padroes-leitor', is_staff=True)

    def test_defaults_have_webp_bytes_and_public_page_uses_live_catalogue(self):
        response = self.client.get('/')
        self.assertContains(response, 'Infraestrutura')
        for equipment in Equipamento.objects.all():
            self.assertTrue(equipment.foto_webp)
            with Image.open(BytesIO(bytes(equipment.foto_webp))) as image:
                self.assertEqual(image.format, 'WEBP')
            self.assertContains(response, equipment.nome)
            photo = self.client.get(reverse('conteudo:equipment-photo', args=[equipment.pk]))
            self.assertEqual(photo.status_code, 200)
            self.assertEqual(photo['Content-Type'], 'image/webp')
            self.assertEqual(b''.join(photo.streaming_content), bytes(equipment.foto_webp))
            close_response(photo)

    def test_restore_recovers_defaults_without_changing_custom_entries_or_ids(self):
        equipment = Equipamento.objects.get(codigo_inicial='impressora-3d')
        original = (equipment.nome, equipment.descricao, bytes(equipment.foto_webp))
        equipment.nome = 'Nome editado'
        equipment.status = 'indisponivel'
        equipment.foto = ''
        equipment.foto_webp = b''
        equipment.save()
        delete_equipment(actor=self.admin, equipment_id=equipment.pk)
        custom = Equipamento.objects.create(nome='Equipamento personalizado', status='ocupado')
        call_command('seed_inovalab', stdout=StringIO())
        equipment.refresh_from_db()
        self.assertIsNotNone(equipment.excluido_em)
        self.assertEqual(equipment.nome, 'Nome editado')
        for _ in range(2):
            restore_default_equipment(actor=self.admin)
        equipment.refresh_from_db()
        self.assertEqual((equipment.nome, equipment.descricao, bytes(equipment.foto_webp)), original)
        self.assertIsNone(equipment.excluido_em)
        self.assertEqual(equipment.status, 'disponivel')
        custom.refresh_from_db()
        self.assertEqual((custom.nome, custom.status), ('Equipamento personalizado', 'ocupado'))
        self.assertEqual(Equipamento.objects.count(), 7)

    def test_confirmation_is_read_only_and_restore_requires_admin_and_csrf(self):
        equipment = Equipamento.objects.first()
        equipment.nome = 'Editado'
        equipment.save()
        url = reverse('catalogo:equipamentos-restore')
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.admin)
        self.assertContains(client.get(url), 'Confirmar restauração')
        equipment.refresh_from_db()
        self.assertEqual(equipment.nome, 'Editado')
        self.assertEqual(client.post(url).status_code, 403)
        token = client.cookies['csrftoken'].value
        self.assertEqual(client.post(url, {'csrfmiddlewaretoken': token}).status_code, 302)
        client.force_login(self.reader)
        self.assertEqual(client.get(url).status_code, 403)
        self.assertEqual(client.post(url, {'csrfmiddlewaretoken': token}).status_code, 403)
        with self.assertRaises(PermissionDenied):
            restore_default_equipment(actor=self.reader)

    def test_uploads_are_converted_and_saved_in_database_and_can_be_cleared(self):
        with TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            machine = save_entry(actor=self.admin, model=Equipamento, data={
                'nome': 'Foto no banco', 'foto': image_upload(), 'status': 'disponivel'})
            machine.refresh_from_db()
            self.assertTrue(machine.foto.name.endswith('.webp'))
            with Image.open(BytesIO(bytes(machine.foto_webp))) as image:
                self.assertEqual(image.format, 'WEBP')
            from pathlib import Path
            self.assertEqual(list(Path(media).iterdir()), [])
            with machine.foto.open('rb') as photo:
                self.assertEqual(photo.read(), bytes(machine.foto_webp))
            machine = save_entry(actor=self.admin, model=Equipamento, instance=machine, data={'foto': False})
            self.assertFalse(machine.foto)
            self.assertFalse(machine.foto_webp)

    def test_deleted_equipment_and_photo_disappear_from_public_site(self):
        equipment = Equipamento.objects.first()
        delete_equipment(actor=self.admin, equipment_id=equipment.pk)
        self.assertNotContains(self.client.get('/'), equipment.nome)
        self.assertEqual(self.client.get(reverse('conteudo:equipment-photo', args=[equipment.pk])).status_code, 404)
