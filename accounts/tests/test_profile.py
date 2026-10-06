from io import BytesIO
from tempfile import TemporaryDirectory
from unittest.mock import patch

from PIL import Image
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings

from accounts.tests.test_identity import PASSWORD


def photo_upload(format='PNG'):
    buffer = BytesIO()
    Image.new('RGB', (600, 400), 'blue').save(buffer, format=format)
    return SimpleUploadedFile('foto.png', buffer.getvalue(), content_type='image/png')


class ProfileTests(TestCase):
    def setUp(self):
        self.enterContext(patch('core.views.load_events', return_value=([], False)))
        self.media = TemporaryDirectory()
        self.addCleanup(self.media.cleanup)
        self.override = override_settings(MEDIA_ROOT=self.media.name)
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.user = get_user_model().objects.create_user('ana', password=PASSWORD)
        self.other = get_user_model().objects.create_user('outra', password=PASSWORD)
        self.client.force_login(self.user)

    def test_edit_own_identity_keeps_session_and_cannot_elevate_privileges(self):
        response = self.client.post('/perfil/', {
            'username':'ana.nova', 'first_name':'Ana', 'last_name':'Silva',
            'is_superuser':'true', 'is_staff':'true', 'id':self.other.pk,
        })
        self.assertRedirects(response, '/perfil/')
        self.user.refresh_from_db()
        self.other.refresh_from_db()
        self.assertEqual((self.user.username, self.user.get_full_name()), ('ana.nova', 'Ana Silva'))
        self.assertFalse(self.user.is_staff or self.user.is_superuser)
        self.assertEqual(self.other.username, 'outra')
        self.assertEqual(int(self.client.session['_auth_user_id']), self.user.pk)
        self.assertTrue(self.user.check_password(PASSWORD))
        self.client.logout()
        self.assertFalse(self.client.login(username='ana.nova', password=PASSWORD))

    def test_duplicate_and_invalid_usernames_leave_account_unchanged(self):
        for username in ('outra', 'nome inválido!', ''):
            response = self.client.post('/perfil/', {'username':username, 'first_name':'Alterado'})
            self.assertEqual(response.status_code, 200)
            self.assertIn('username', response.context['form'].errors)
            self.user.refresh_from_db()
            self.assertEqual((self.user.username, self.user.first_name), ('ana', ''))

    def test_upload_normalized_photo_and_preserve_without_new_upload(self):
        self.assertRedirects(self.client.post('/perfil/', {'username':'ana', 'foto':photo_upload()}), '/perfil/')
        self.user.refresh_from_db()
        filename = self.user.foto.name
        response = self.client.get(f'/usuarios/{self.user.pk}/foto/')
        self.assertEqual(response['Content-Type'], 'image/webp')
        self.assertIn('no-store', response['Cache-Control'])
        image = Image.open(BytesIO(b''.join(response.streaming_content)))
        self.assertEqual(image.format, 'WEBP')
        self.assertLessEqual(max(image.size), 512)
        response.close()
        self.assertRedirects(self.client.post('/perfil/', {'username':'ana', 'first_name':'Ana'}), '/perfil/')
        self.user.refresh_from_db()
        self.assertEqual(self.user.foto.name, filename)
        self.assertContains(self.client.get('/index/'), f'/usuarios/{self.user.pk}/foto/')

    def test_invalid_large_or_unsupported_photo_does_not_save(self):
        uploads = [SimpleUploadedFile('foto.png', b'nao e imagem'), photo_upload('GIF'),
                   SimpleUploadedFile('grande.png', b'x' * (5 * 1024 * 1024 + 1))]
        for upload in uploads:
            response = self.client.post('/perfil/', {'username':'ana.nova', 'foto':upload})
            self.assertIn('foto', response.context['form'].errors)
            self.user.refresh_from_db()
            self.assertFalse(self.user.foto)
            self.assertEqual(self.user.username, 'ana')

    def test_profile_requires_csrf_and_photo_requires_authorized_viewer(self):
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.user)
        self.assertEqual(strict.post('/perfil/', {'username':'nova'}).status_code, 403)
        self.assertEqual(self.client.get(f'/usuarios/{self.other.pk}/foto/').status_code, 403)
        self.assertEqual(self.client.get(f'/usuarios/{self.user.pk}/foto/').status_code, 404)
        self.client.logout()
        self.assertEqual(self.client.post('/perfil/', {'username':'nova'}).status_code, 302)
        self.assertEqual(self.client.get(f'/usuarios/{self.user.pk}/foto/').status_code, 302)

    def test_superuser_can_consult_photo_without_changing_account(self):
        self.client.post('/perfil/', {'username':'ana', 'foto':photo_upload()})
        admin = get_user_model().objects.create_superuser('admin', password=PASSWORD)
        self.client.force_login(admin)
        response = self.client.get(f'/usuarios/{self.user.pk}/foto/')
        self.assertEqual(response.status_code, 200)
        response.close()
