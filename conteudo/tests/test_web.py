from datetime import datetime, timedelta
from unittest.mock import patch

from django.test import Client, TestCase

from conteudo.models import Banner
from conteudo.services import save_banner
from conteudo.tests.helpers import DATA, BannerFixtures, image_upload


class BannerWebTests(BannerFixtures, TestCase):
    def setUp(self):
        super().setUp()
        self.banner = save_banner(actor=self.admin, data=DATA, image=image_upload())
        self.detail = f'/banners/{self.banner.pk}/'
        self.image = self.detail + 'imagem/'

    def test_anonymous_redirects_and_staff_denied_admin_pages(self):
        paths = ('/banners/', '/banners/novo/', self.detail, self.detail+'editar/', self.detail+'excluir/')
        for path in paths:
            self.assertEqual(self.client.get(path).status_code, 302)
        self.client.force_login(self.user)
        for path in paths:
            self.assertEqual(self.client.get(path).status_code, 403)
        self.assertNotContains(self.client.get('/'), '/banners/')

    def test_admin_creates_webp_with_csrf_and_edits_without_reupload(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.admin)
        client.get('/banners/novo/')
        self.assertEqual(client.post('/banners/novo/', {**DATA, 'banner_img': image_upload()}).status_code, 403)
        data = {**DATA, 'banner_img': image_upload(), 'csrfmiddlewaretoken': client.cookies['csrftoken'].value}
        response = client.post('/banners/novo/', data)
        self.assertEqual(response.status_code, 302)
        self.assertContains(client.get('/'), '/banners/')
        response = client.post(self.detail+'editar/', {**DATA, 'titulo': 'Editado', 'versao': 1,
                              'csrfmiddlewaretoken': client.cookies['csrftoken'].value})
        self.assertEqual(response.status_code, 302)
        self.banner.refresh_from_db()
        self.assertEqual((self.banner.titulo, self.banner.versao), ('Editado', 2))

    def test_invalid_upload_and_unknown_fields_never_save(self):
        self.client.force_login(self.admin)
        for data in ({**DATA, 'banner_img': image_upload(format='PNG')}, {**DATA, 'banner_img': image_upload(), 'extra': 'x'}):
            response = self.client.post('/banners/novo/', data)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context['form'].errors)
        self.assertEqual(Banner.objects.count(), 1)

    def test_form_schedule_brasilia_and_stale_version_preserved(self):
        self.client.force_login(self.admin)
        body = {**DATA, 'status': 'agendado', 'inicio_exibicao': '2026-11-01T10:00:00',
                'fim_exibicao': '2026-11-01T11:00:00', 'versao': 1}
        self.assertEqual(self.client.post(self.detail+'editar/', body).status_code, 302)
        self.banner.refresh_from_db()
        self.assertEqual(self.banner.inicio_exibicao.isoformat(), '2026-11-01T13:00:00+00:00')
        stale = self.client.post(self.detail+'editar/', body)
        self.assertEqual(stale.status_code, 409)
        self.assertEqual(stale.context['form']['versao'].value(), '1')

    def test_public_pages_only_show_eligible_local_images(self):
        hidden = save_banner(actor=self.admin, data={**DATA, 'titulo': 'Privado', 'status': 'inativo'}, image=image_upload())
        home = self.client.get('/publico/')
        self.assertContains(home, self.image)
        self.assertNotContains(home, 'Privado')
        self.assertNotContains(self.client.get('/publico/sobre/'), self.image)
        self.assertIn('no-store', home['Cache-Control'])
        self.assertEqual(self.client.get(f'/banners/{hidden.pk}/imagem/').status_code, 404)
        self.assertEqual(self.client.get('/').status_code, 302)

    def test_image_route_hides_unpublished_but_allows_admin_preview(self):
        save_banner(actor=self.admin, banner_id=self.banner.pk, expected_version=1, data={'status': 'inativo'})
        self.assertEqual(self.client.get(self.image).status_code, 404)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(self.image).status_code, 404)
        self.client.force_login(self.admin)
        response = self.client.get(self.image)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'image/webp')
        self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
        self.assertIn('no-store', response['Cache-Control'])
        response.close()
        self.assertEqual(self.client.get('/media/'+self.banner.banner_img.name).status_code, 404)

    def test_image_has_same_schedule_boundaries_as_html(self):
        start = datetime.fromisoformat('2026-11-01T10:00:00-03:00')
        save_banner(actor=self.admin, banner_id=self.banner.pk, expected_version=1, data={
            'status': 'agendado', 'inicio_exibicao': start, 'fim_exibicao': start+timedelta(hours=1)})
        for now, status in ((start-timedelta(seconds=1), 404), (start, 200), (start+timedelta(hours=1), 404)):
            with patch('conteudo.selectors.timezone.now', return_value=now):
                response = self.client.get(self.image)
                self.assertEqual(response.status_code, status)
                response.close()

    def test_image_and_publication_are_read_from_same_version(self):
        save_banner(actor=self.admin, banner_id=self.banner.pk, expected_version=1, data={'status': 'inativo'})
        public_image = image_upload(color='red')
        expected_bytes = public_image.read()
        public_image.seek(0)
        from conteudo.selectors import published_banners

        def replace_and_publish(*args, **kwargs):
            save_banner(actor=self.admin, banner_id=self.banner.pk, expected_version=2,
                        data={'status': 'ativo'}, image=public_image)
            return published_banners(*args, **kwargs)

        with patch('conteudo.views.published_banners', side_effect=replace_and_publish):
            response = self.client.get(self.image)
            try:
                self.assertEqual(response.status_code, 200)
                self.assertEqual(b''.join(response.streaming_content), expected_bytes)
            finally:
                response.close()

    def test_image_not_found_responses_cannot_cache_publication_state(self):
        save_banner(actor=self.admin, banner_id=self.banner.pk, expected_version=1, data={'status': 'inativo'})
        for path in (self.image, '/banners/99999/imagem/'):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 404)
            self.assertIn('no-store', response.get('Cache-Control', ''))
        self.client.force_login(self.admin)
        self.banner.banner_img.storage.delete(self.banner.banner_img.name)
        response = self.client.get(self.image)
        self.assertEqual(response.status_code, 404)
        self.assertIn('no-store', response.get('Cache-Control', ''))

    def test_exclusion_get_only_confirms_and_post_requires_version(self):
        self.client.force_login(self.admin)
        self.assertContains(self.client.get(self.detail+'excluir/'), DATA['titulo'])
        self.banner.refresh_from_db()
        self.assertIsNone(self.banner.excluido_em)
        self.assertEqual(self.client.post(self.detail+'excluir/', {}).status_code, 400)
        self.assertEqual(self.client.post(self.detail+'excluir/', {'versao': 1}).status_code, 302)
        self.assertEqual(self.client.get(self.detail).status_code, 404)
        self.assertEqual(self.client.get(self.image).status_code, 404)

    def test_list_is_paginated_and_private_responses_not_cached(self):
        Banner.objects.bulk_create([Banner(**{**DATA, 'titulo': f'Lista {i:02}', 'banner_img': self.banner.banner_img.name})
                                   for i in range(25)])
        self.client.force_login(self.admin)
        response = self.client.get('/banners/')
        self.assertEqual(len(response.context['object_list']), 25)
        self.assertIn('no-store', response['Cache-Control'])
        self.assertEqual(len(self.client.get('/banners/?page=2').context['object_list']), 1)
