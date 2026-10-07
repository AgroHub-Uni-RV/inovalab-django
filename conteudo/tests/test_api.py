from datetime import datetime, timedelta
from unittest.mock import patch

from django.contrib.auth.models import Group
from django.test import Client, TestCase

from conteudo.models import Banner
from conteudo.services import delete_banner, save_banner
from conteudo.tests.helpers import DATA, BannerFixtures, image_upload


class BannerApiTests(BannerFixtures, TestCase):
    def setUp(self):
        super().setUp()
        self.banner = save_banner(actor=self.admin, data=DATA, image=image_upload())
        self.path = f'/api/v1/banners/{self.banner.pk}/'

    def test_admin_read_denied_to_anonymous_staff_and_bearer_token(self):
        token = 'credencial-sem-autenticacao-por-sessao'
        self.assertEqual(self.client.get('/api/v1/banners/').status_code, 403)
        self.assertEqual(self.client.get(self.path, HTTP_AUTHORIZATION=f'Bearer {token}').status_code, 403)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(self.path).status_code, 403)
        self.assertEqual(self.client.patch(self.path, {'versao': 1, 'titulo': 'Negado'},
                                          content_type='application/json').status_code, 403)

    def test_business_admin_without_staff_creates_multipart_and_edits_json(self):
        self.user.is_staff = False
        self.user.save(update_fields=['is_staff'])
        self.user.groups.add(Group.objects.get(name='Administradores'))
        self.client.force_login(self.user)
        response = self.client.post('/api/v1/banners/', {**DATA, 'banner_img': image_upload(), 'ordem': '2'})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['ordem'], 2)
        self.assertNotIn('banner_img', response.json())
        self.assertIn('/imagem/', response.json()['imagem_url'])
        changed = self.client.patch(self.path, {'titulo': 'Alterado', 'versao': 1}, content_type='application/json')
        self.assertEqual(changed.status_code, 200)
        self.assertEqual((changed.json()['titulo'], changed.json()['versao']), ('Alterado', 2))

    def test_multipart_patch_replaces_image_and_preserves_omitted_fields(self):
        self.client.force_login(self.admin)
        old_name = self.banner.banner_img.name
        from django.test.client import encode_multipart
        response = self.client.patch(self.path, encode_multipart('banner-boundary', {
            'banner_img': image_upload(color='red'), 'versao': '1',
        }), content_type='multipart/form-data; boundary=banner-boundary')
        self.assertEqual(response.status_code, 200, response.content)
        self.banner.refresh_from_db()
        self.assertNotEqual(self.banner.banner_img.name, old_name)
        self.assertEqual(self.banner.titulo, DATA['titulo'])

    def test_public_catalog_requires_local_and_only_exposes_eligible_fields(self):
        self.assertEqual(self.client.get('/api/v1/publico/banners/').status_code, 400)
        self.assertEqual(self.client.get('/api/v1/publico/banners/?local=admin').status_code, 400)
        save_banner(actor=self.admin, data={**DATA, 'titulo': 'Privado', 'status': 'inativo'}, image=image_upload())
        response = self.client.get('/api/v1/publico/banners/?local=home')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['count'], 1)
        self.assertEqual(set(data['results'][0]), {'id', 'titulo', 'texto_alternativo', 'imagem_url', 'local', 'ordem'})
        self.assertEqual(data['results'][0]['texto_alternativo'], 'Laboratório')
        self.assertIn('no-store', response['Cache-Control'])
        self.assertEqual(self.client.get('/api/v1/publico/banners/?local=sobre').json()['count'], 0)

    def test_publication_exact_boundaries_and_pagination(self):
        start = datetime.fromisoformat('2026-11-01T10:00:00-03:00')
        scheduled = save_banner(actor=self.admin, data={**DATA, 'status': 'agendado', 'ordem': 0,
            'inicio_exibicao': start, 'fim_exibicao': start + timedelta(hours=1)}, image=image_upload())
        for instant, count in ((start-timedelta(seconds=1), 1), (start, 2), (start+timedelta(hours=1), 1)):
            with patch('conteudo.selectors.timezone.now', return_value=instant):
                self.assertEqual(self.client.get('/api/v1/publico/banners/?local=home').json()['count'], count)
        Banner.objects.bulk_create([Banner(**{**DATA, 'titulo': f'Banner {i:02}', 'banner_img': self.banner.banner_img.name})
                                   for i in range(25)])
        self.assertEqual(len(self.client.get('/api/v1/publico/banners/?local=home').json()['results']), 25)
        self.assertEqual(len(self.client.get('/api/v1/publico/banners/?local=home&page=2').json()['results']), 1)
        self.assertFalse(self.client.get('/api/v1/publico/banners/?local=home').json()['results'][0]['id'] == scheduled.pk)

    def test_strict_payload_and_versions_do_not_write(self):
        self.client.force_login(self.admin)
        for body in ({'titulo': 'Sem versão'}, {'id': 9, 'versao': 1}, {'excluido_em': None, 'versao': 1},
                     {'versao': True}, {'versao': '1'}, {'versao': 1.0}, {'versao': 1, 'ordem': True},
                     {'versao': 1, 'ordem': 1.5}, {'versao': 1, 'ordem': 2147483648}, [DATA]):
            with self.subTest(body=body):
                self.assertEqual(self.client.patch(self.path, body, content_type='application/json').status_code, 400)
        self.assertEqual(self.client.post('/api/v1/banners/', {**DATA, 'banner_img': image_upload(), 'versao': '1'}).status_code, 400)
        self.banner.refresh_from_db()
        self.assertEqual((self.banner.titulo, self.banner.versao), (DATA['titulo'], 1))

    def test_invalid_upload_and_time_are_rejected(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.post('/api/v1/banners/', {**DATA, 'banner_img': image_upload(format='PNG')}).status_code, 400)
        for body in ({'status': 'agendado'}, {'status': 'agendado', 'inicio_exibicao': '2026-11-01T10:00:00',
                                             'fim_exibicao': '2026-11-01T11:00:00-03:00'},
                     {'status': 'ativo', 'inicio_exibicao': '2026-11-01T10:00:00-03:00'}):
            self.assertEqual(self.client.patch(self.path, {**body, 'versao': 1}, content_type='application/json').status_code, 400)

    def test_put_requires_complete_fields_but_retains_image(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.put(self.path, {'versao': 1, 'titulo': 'Incompleto'},
                                        content_type='application/json').status_code, 400)
        response = self.client.put(self.path, {**DATA, 'versao': 1, 'status': 'inativo'}, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.banner.refresh_from_db()
        self.assertEqual(self.banner.status, 'inativo')
        self.assertEqual(len(self.stored_files()), 1)

    def test_stale_edit_and_delete_preserve_winner(self):
        self.client.force_login(self.admin)
        self.client.patch(self.path, {'versao': 1, 'titulo': 'Vencedor'}, content_type='application/json')
        for response in (self.client.patch(self.path, {'versao': 1, 'titulo': 'Perdedor'}, content_type='application/json'),
                         self.client.delete(self.path, {'versao': 1}, content_type='application/json')):
            self.assertEqual(response.status_code, 409)
            self.assertEqual(response.json()['code'], 'versao_desatualizada')
        self.banner.refresh_from_db()
        self.assertEqual((self.banner.titulo, self.banner.versao), ('Vencedor', 2))
        self.assertIsNone(self.banner.excluido_em)

    def test_delete_requires_version_and_removes_public_and_admin_access(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.delete(self.path, {}, content_type='application/json').status_code, 400)
        self.assertEqual(self.client.delete(self.path, {'versao': 1}, content_type='application/json').status_code, 204)
        self.assertEqual(self.client.get(self.path).status_code, 404)
        self.assertEqual(self.client.get('/api/v1/publico/banners/?local=home').json()['count'], 0)
        self.assertEqual(self.client.get(f'/banners/{self.banner.pk}/imagem/').status_code, 404)

    def test_csrf_and_account_revocation_apply_to_admin_api(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.admin)
        client.get('/perfil/')
        self.assertEqual(client.patch(self.path, {'versao': 1, 'titulo': 'Negado'}, content_type='application/json').status_code, 403)
        response = client.patch(self.path, {'versao': 1, 'titulo': 'Aceito'}, content_type='application/json',
                                HTTP_X_CSRFTOKEN=client.cookies['csrftoken'].value)
        self.assertEqual(response.status_code, 200)
        self.admin.is_active = False
        self.admin.save(update_fields=['is_active'])
        self.assertEqual(client.get(self.path).status_code, 403)

    def test_public_api_is_read_only_and_defaults_alt_to_title(self):
        save_banner(actor=self.admin, banner_id=self.banner.pk, expected_version=1, data={'texto_alternativo': ''})
        item = self.client.get('/api/v1/publico/banners/?local=home').json()['results'][0]
        self.assertEqual(item['texto_alternativo'], DATA['titulo'])
        self.assertEqual(self.client.post('/api/v1/publico/banners/?local=home', DATA).status_code, 405)
