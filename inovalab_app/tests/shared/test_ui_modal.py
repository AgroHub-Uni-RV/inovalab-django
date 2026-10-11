from django.test import Client, TestCase

from inovalab_app.catalogo.models import Equipamento
from inovalab_app.conteudo.models import Banner
from inovalab_app.materiais.models import Material
from inovalab_app.tests.conteudo.helpers import BannerFixtures, DATA, image_upload


class ModalFormTests(BannerFixtures, TestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.admin)

    def test_modal_success_is_explicit_only_after_persistence(self):
        cases = (
            ('/catalogo/equipamentos/novo/', Equipamento, {'nome': 'Microscópio', 'status': 'disponivel'}),
            ('/materiais/novo/', Material, {'nome': 'PLA', 'categoria': 'Filamento', 'quantidade': '2,5',
                                         'unidade': 'kg', 'status': 'disponivel', 'fonte': 'Compra'}),
            ('/banners/novo/', Banner, {**DATA, 'banner_img': image_upload()}),
        )
        for url, model, data in cases:
            with self.subTest(url=url):
                self.assertContains(self.client.get(url, HTTP_X_UI_MODAL='1'), 'data-ui-modal-page')
                response = self.client.post(url, data, HTTP_X_UI_MODAL='1')
                self.assertEqual(response.status_code, 200)
                saved = model.objects.latest('pk')
                self.assertEqual(response.json(), {'saved': True, 'redirect_url': url.replace('novo/', f'{saved.pk}/')})
                self.assertIn('no-store', response['Cache-Control'])

    def test_invalid_modal_never_reports_success_and_retains_fields(self):
        response = self.client.post('/materiais/novo/', {'nome': 'PLA', 'categoria': 'Filamento',
            'quantidade': '-1', 'unidade': 'kg', 'status': 'disponivel'}, HTTP_X_UI_MODAL='1')
        self.assertContains(response, 'data-ui-modal-page')
        self.assertContains(response, 'value="PLA"')
        self.assertTrue(response.context['form'].errors)
        self.assertEqual(Material.objects.count(), 0)

    def test_modal_preserves_csrf_permissions_and_no_js_redirect(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.admin)
        self.assertEqual(client.post('/materiais/novo/', {}, HTTP_X_UI_MODAL='1').status_code, 403)
        self.client.force_login(self.user)
        for url in ('/materiais/novo/', '/banners/novo/', '/catalogo/equipamentos/novo/'):
            self.assertEqual(self.client.post(url, {}, HTTP_X_UI_MODAL='1').status_code, 403)
        self.client.force_login(self.admin)
        response = self.client.post('/catalogo/equipamentos/novo/', {'nome': 'Teste', 'status': 'disponivel'})
        self.assertEqual(response.status_code, 302)

    def test_stale_modal_edit_returns_conflict_without_overwriting(self):
        material = Material.objects.create(nome='PLA', categoria='Filamento', quantidade=1,
                                           unidade='kg', status='disponivel')
        url = f'/materiais/{material.pk}/editar/'
        data = {'nome': 'Novo nome', 'categoria': 'Filamento', 'quantidade': '1', 'unidade': 'kg',
                'status': 'disponivel', 'fonte': 'Compra', 'versao': material.versao}
        self.assertTrue(self.client.post(url, data, HTTP_X_UI_MODAL='1').json()['saved'])
        response = self.client.post(url, {**data, 'nome': 'Nome desatualizado'}, HTTP_X_UI_MODAL='1')
        self.assertContains(response, 'data-ui-modal-page', status_code=409)
        material.refresh_from_db()
        self.assertEqual(material.nome, 'Novo nome')
