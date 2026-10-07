from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from inovalab_app.conteudo.models import Banner
from inovalab_app.conteudo.services import save_banner, delete_banner
from inovalab_app.tests.conteudo.helpers import BannerFixtures, DATA, image_upload


class BannerFrontendTests(BannerFixtures, TestCase):
    def setUp(self):
        super().setUp()
        self.banner = save_banner(actor=self.admin, data=DATA, image=image_upload())
        save_banner(actor=self.admin, data={**DATA, 'titulo':'Privado', 'status':'inativo'}, image=image_upload())
        now = timezone.now()
        save_banner(actor=self.admin, data={**DATA, 'titulo':'Futuro', 'status':'agendado',
                    'inicio_exibicao':now+timedelta(days=1), 'fim_exibicao':now+timedelta(days=2)}, image=image_upload())
        deleted = save_banner(actor=self.admin, data={**DATA, 'titulo':'Excluído'}, image=image_upload())
        delete_banner(actor=self.admin, banner_id=deleted.pk, expected_version=1)
        self.client.force_login(self.admin)

    def test_status_tabs_count_non_deleted_and_protected_thumbnail_routes(self):
        response = self.client.get('/banners/', {'status':'inativo'})
        self.assertEqual(response.context['stat_counts'], {'total':3, 'ativo':1, 'inativo':1, 'agendado':1})
        self.assertEqual(response.context['paginator'].count, 1)
        self.assertContains(response, '/imagem/')
        self.assertNotContains(response, '/media/')
        self.assertNotContains(response, 'Excluído')
        self.client.force_login(self.user)
        self.assertEqual(self.client.get('/banners/', {'status':'inativo'}).status_code, 403)

    def test_search_and_invalid_tab_normalization(self):
        response = self.client.get('/banners/', {'q':'Futuro', 'status':'desconhecido'})
        self.assertEqual(response.context['selected_status'], '')
        self.assertEqual(response.context['paginator'].count, 1)
        self.assertEqual(response.context['stat_counts']['total'], 1)
        self.assertIn('no-store', response['Cache-Control'])

    def test_pagination_preserves_search_and_tab(self):
        Banner.objects.bulk_create([Banner(**{**DATA, 'titulo':f'Busca {i:02}', 'banner_img':self.banner.banner_img.name}) for i in range(26)])
        first = self.client.get('/banners/', {'q':'Busca', 'status':'ativo'})
        self.assertEqual(first.context['paginator'].count, 26)
        self.assertContains(first, 'q=Busca')
        self.assertContains(first, 'status=ativo')
        self.assertEqual(len(self.client.get('/banners/', {'q':'Busca', 'status':'ativo', 'page':2}).context['object_list']), 1)

    def test_authenticated_pages_keep_internal_navigation_and_publication_filter(self):
        for actor in (self.admin, self.user):
            self.client.force_login(actor)
            for path in ('/publico/', '/publico/sobre/'):
                with self.subTest(actor=actor.username, path=path):
                    response = self.client.get(path)
                    self.assertTemplateUsed(response, 'inovalab_app/shared/base.html')
                    self.assertContains(response, 'id="sidebar"')
                    self.assertContains(response, 'class="topbar"')
                    self.assertContains(response, 'class="footer"')
                    self.assertNotContains(response, 'Privado')
                    self.assertNotContains(response, 'Futuro')
                    self.assertNotContains(response, 'Excluído')

    def test_anonymous_pages_keep_public_layout_without_account_information(self):
        self.client.logout()
        for path in ('/publico/', '/publico/sobre/'):
            response = self.client.get(path)
            self.assertTemplateUsed(response, 'inovalab_app/shared/public_base.html')
            self.assertNotContains(response, 'id="sidebar"')
            self.assertNotContains(response, '/sair/')
