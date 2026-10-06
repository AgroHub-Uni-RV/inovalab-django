from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client, TestCase

from materiais.models import Material
from materiais.services import save_material
from materiais.tests.test_services import DATA


class MaterialWebTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_user('web-gestor-material')
        cls.admin.groups.add(Group.objects.get(name='Administradores'))
        cls.user = get_user_model().objects.create_user('web-leitor-material', is_staff=True)
        cls.material = save_material(actor=cls.admin, data=DATA)

    def setUp(self):
        self.detail = f'/materiais/{self.material.pk}/'
        self.edit = self.detail + 'editar/'

    def test_anonymous_redirects_on_all_pages(self):
        for path in ('/materiais/', '/materiais/novo/', self.detail, self.edit):
            self.assertRedirects(self.client.get(path), f'/?next={path}', fetch_redirect_response=False)

    def test_reader_consults_without_write_links(self):
        self.client.force_login(self.user)
        self.assertContains(self.client.get('/perfil/'), '/materiais/')
        for path in ('/materiais/', self.detail):
            response = self.client.get(path)
            self.assertContains(response, 'Filamento')
            self.assertNotContains(response, '/materiais/novo/')
            self.assertNotContains(response, self.edit)
        self.assertContains(self.client.get(self.detail), 'Compra do laboratório')

    def test_staff_without_business_role_cannot_write_by_url(self):
        self.client.force_login(self.user)
        for path in ('/materiais/novo/', self.edit):
            self.assertEqual(self.client.get(path).status_code, 403)
            self.assertEqual(self.client.post(path, {**DATA, 'versao': 1}).status_code, 403)
        self.assertEqual(Material.objects.count(), 1)

    def test_admin_creates_with_portuguese_decimal(self):
        self.client.force_login(self.admin)
        self.assertContains(self.client.get('/materiais/'), '/materiais/novo/')
        response = self.client.post('/materiais/novo/', {**DATA, 'nome': ' Criado ', 'quantidade': '1,125'})
        created = Material.objects.get(nome='Criado')
        self.assertRedirects(response, f'/materiais/{created.pk}/', fetch_redirect_response=False)
        self.assertEqual(str(created.quantidade), '1.125')

    def test_correction_preserves_id_and_rejects_stale_form(self):
        self.client.force_login(self.admin)
        response = self.client.post(self.edit, {**DATA, 'quantidade': '8', 'versao': 1})
        self.assertRedirects(response, self.detail)
        stale = self.client.post(self.edit, {**DATA, 'nome': 'Perdedor', 'quantidade': '99', 'versao': 1})
        self.assertEqual(stale.status_code, 409)
        self.material.refresh_from_db()
        self.assertEqual((self.material.nome, str(self.material.quantidade), self.material.versao),
                         ('Filamento', '8.000', 2))
        self.assertEqual(stale.context['form']['versao'].value(), '1')

    def test_zero_and_upper_decimal_limit_match_api_and_domain(self):
        self.client.force_login(self.admin)
        for quantity in ('0', '999999999,999'):
            with self.subTest(quantity=quantity):
                response = self.client.post('/materiais/novo/', {**DATA, 'quantidade': quantity})
                self.assertEqual(response.status_code, 302, response.context['form'].errors if response.status_code != 302 else '')

    def test_invalid_forms_preserve_data_and_missing_version_is_400(self):
        self.client.force_login(self.admin)
        for change in ({'quantidade': '-1'}, {'quantidade': '0,0001'}, {'nome': ' '}, {'status': 'devolvido'},
                       {'extra': 'negado'}):
            response = self.client.post(self.edit, {**DATA, **change, 'versao': 1})
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context['form'].errors)
        self.assertEqual(self.client.post(self.edit, DATA).status_code, 400)
        self.material.refresh_from_db()
        self.assertEqual(self.material.versao, 1)

    def test_web_requires_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.admin)
        client.get('/materiais/novo/')
        self.assertEqual(client.post('/materiais/novo/', DATA).status_code, 403)
        response = client.post('/materiais/novo/', {**DATA, 'csrfmiddlewaretoken': client.cookies['csrftoken'].value})
        self.assertEqual(response.status_code, 302)

    def test_list_paginates_and_unavailable_remains_consultable(self):
        Material.objects.bulk_create([Material(**{**DATA, 'nome': f'Item {i:02}', 'status': 'indisponivel'})
                                      for i in range(25)])
        self.client.force_login(self.user)
        first = self.client.get('/materiais/')
        second = self.client.get('/materiais/?page=2')
        self.assertEqual(len(first.context['object_list']), 25)
        self.assertEqual(len(second.context['object_list']), 1)
        self.assertContains(first, 'Indisponível')

    def test_disabled_session_cannot_read_materials(self):
        self.client.force_login(self.admin)
        self.admin.is_active = False
        self.admin.save(update_fields=['is_active'])
        self.assertEqual(self.client.get('/materiais/').status_code, 302)
