from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from catalogo.models import Equipamento
from conteudo.tests.helpers import image_upload


class EquipmentPhotoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_user('gestor_fotos')
        cls.admin.groups.add(Group.objects.get(name='Administradores'))
        cls.user = get_user_model().objects.create_user('leitor_fotos')

    def test_seeded_equipment_cards_have_working_photos_and_single_selection(self):
        self.client.force_login(self.user)
        response = self.client.get('/agenda/novo/?categoria=equipamento')
        self.assertContains(response, 'equipment-picker')
        for machine in Equipamento.objects.filter(codigo_inicial__isnull=False):
            self.assertTrue(machine.foto)
            self.assertTrue(machine.foto.name.endswith('.webp'))
            self.assertContains(response, machine.foto.url)
            photo = self.client.get(machine.foto.url)
            self.assertEqual(photo.status_code, 200)
            self.assertEqual(photo['Content-Type'], 'image/webp')
            self.assertTrue(b''.join(photo.streaming_content))
            photo.close()

    def test_admin_can_upload_replace_and_clear_photo_but_normal_user_cannot(self):
        with TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            self.client.force_login(self.admin)
            response = self.client.post('/catalogo/equipamentos/novo/', {'nome': 'Máquina com foto',
                'descricao': 'Descrição', 'status': 'disponivel', 'foto': image_upload()})
            machine = Equipamento.objects.get(nome='Máquina com foto')
            self.assertRedirects(response, f'/catalogo/equipamentos/{machine.pk}/')
            self.assertTrue(machine.foto)
            self.assertContains(self.client.get(f'/catalogo/equipamentos/{machine.pk}/'), machine.foto.url)
            photo = self.client.get(machine.foto.url)
            self.assertEqual(photo.status_code, 200)
            self.assertTrue(b''.join(photo.streaming_content))
            photo.close()
            original = machine.foto.name
            self.client.force_login(self.user)
            self.assertEqual(self.client.post(f'/catalogo/equipamentos/{machine.pk}/editar/',
                             {'foto': image_upload()}).status_code, 403)
            self.client.force_login(self.admin)
            url = f'/catalogo/equipamentos/{machine.pk}/editar/'
            self.client.post(url, {'nome': machine.nome, 'descricao': '', 'status': 'disponivel', 'foto': image_upload()})
            machine.refresh_from_db()
            self.assertNotEqual(machine.foto.name, original)
            self.client.post(url, {'nome': machine.nome, 'descricao': '', 'status': 'disponivel', 'foto-clear': 'on'})
            machine.refresh_from_db()
            self.assertFalse(machine.foto)

    def test_invalid_image_is_rejected_and_unpictured_equipment_has_placeholder(self):
        self.client.force_login(self.admin)
        invalid = SimpleUploadedFile('foto.png', b'not an image', content_type='image/png')
        response = self.client.post('/catalogo/equipamentos/novo/', {'nome': 'Inválido', 'descricao': '',
                                   'status': 'disponivel', 'foto': invalid})
        self.assertEqual(response.status_code, 200)
        self.assertIn('foto', response.context['form'].errors)
        self.assertFalse(Equipamento.objects.filter(nome='Inválido').exists())
        machine = Equipamento.objects.create(nome='Máquina sem foto')
        response = self.client.get('/agenda/novo/?categoria=equipamento')
        self.assertContains(response, 'Sem foto')
        self.assertContains(response, machine.nome)

    def test_photo_endpoint_requires_login_and_cannot_serve_unrelated_files(self):
        machine = Equipamento.objects.filter(codigo_inicial='impressora-3d').get()
        self.assertTrue(machine.foto)
        self.assertEqual(self.client.get(machine.foto.url).status_code, 302)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get('/catalogo/equipamentos/foto/', {'arquivo': 'perfis/privado.webp'}).status_code, 404)
        self.assertEqual(self.client.get('/catalogo/equipamentos/foto/', {'arquivo': '../db.sqlite3'}).status_code, 404)
        self.assertEqual(self.client.get('/catalogo/equipamentos/foto/').status_code, 404)

    def test_equipment_api_supports_photo_upload_and_read(self):
        with TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            client = APIClient()
            client.force_login(self.admin)
            response = client.post('/api/v1/equipamentos/', {'nome': 'Máquina API', 'descricao': '',
                'status': 'disponivel', 'foto': image_upload()}, format='multipart')
            self.assertEqual(response.status_code, 201)
            self.assertTrue(response.data['foto'])

    def test_equipment_selection_persists_on_error_and_photo_appears_in_booking_detail(self):
        self.client.force_login(self.user)
        machine = Equipamento.objects.get(codigo_inicial='impressora-3d')
        data = {'categoria': 'equipamento', 'objeto': machine.pk, 'requerente': '', 'motivo': 'Protótipo',
                'inicio': '2026-11-01T14:00:00', 'fim': '2026-11-01T15:00:00'}
        response = self.client.post('/agenda/novo/', data)
        options = response.context['form'].fields['objeto'].widget.optgroups('objeto', [str(machine.pk)])
        selected = [option for _, options, _ in options for option in options if option['selected']]
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0]['value'].value, machine.pk)
        response = self.client.post('/agenda/novo/', {**data, 'requerente': 'Meu projeto'})
        self.assertEqual(response.status_code, 302)
        self.assertContains(self.client.get(response.url), machine.foto.url)
