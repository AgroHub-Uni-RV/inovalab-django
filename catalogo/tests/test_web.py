from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client, TestCase

from accounts.tests.test_identity import PASSWORD
from catalogo.models import Equipamento, Espaco, Servico


CASES = (
    ('servicos', Servico, {'nome': 'Novo serviço', 'descricao': 'Descrição', 'status': 'disponivel'}),
    ('equipamentos', Equipamento, {'nome': 'Impressora', 'descricao': 'Descrição', 'status': 'ocupado'}),
    ('espacos', Espaco, {'nome': 'Sala', 'capacidade_maxima_de_pessoas': 10, 'status': 'disponivel'}),
)


class CatalogWebTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_user('gestor', password=PASSWORD)
        cls.admin.groups.add(Group.objects.get(name='Administradores'))
        cls.user = get_user_model().objects.create_user('leitor', password=PASSWORD)
        cls.entries = {slug: model.objects.create(**data) for slug, model, data in CASES}

    def test_anonymous_redirects_to_login_for_all_categories(self):
        for slug, _, _ in CASES:
            path = f'/catalogo/{slug}/'
            self.assertRedirects(self.client.get(path), f'/entrar/?next={path}', fetch_redirect_response=False)

    def test_internal_user_can_read_all_categories_without_write_links(self):
        self.client.force_login(self.user)
        for slug, _, _ in CASES:
            with self.subTest(slug=slug):
                response = self.client.get(f'/catalogo/{slug}/')
                self.assertContains(response, self.entries[slug].nome)
                self.assertNotContains(response, f'/catalogo/{slug}/novo/')
                detail = self.client.get(f'/catalogo/{slug}/{self.entries[slug].pk}/')
                self.assertContains(detail, self.entries[slug].nome)
                self.assertNotContains(detail, '/editar/')

    def test_regular_and_staff_cannot_write_by_direct_url(self):
        for staff in (False, True):
            self.user.is_staff = staff
            self.user.save(update_fields=['is_staff'])
            self.client.force_login(self.user)
            for slug, model, data in CASES:
                with self.subTest(slug=slug, staff=staff):
                    count = model.objects.count()
                    for path in (f'/catalogo/{slug}/novo/', f'/catalogo/{slug}/{self.entries[slug].pk}/editar/'):
                        self.assertEqual(self.client.get(path).status_code, 403)
                        self.assertEqual(self.client.post(path, data).status_code, 403)
                    self.assertEqual(model.objects.count(), count)

    def test_business_admin_without_staff_can_create_each_category(self):
        self.assertFalse(self.admin.is_staff)
        self.client.force_login(self.admin)
        for slug, model, data in CASES:
            with self.subTest(slug=slug):
                self.assertContains(self.client.get(f'/catalogo/{slug}/'), f'/catalogo/{slug}/novo/')
                response = self.client.post(f'/catalogo/{slug}/novo/', {**data, 'nome': '  Criado pela interface  '})
                entry = model.objects.get(nome='Criado pela interface')
                self.assertRedirects(response, f'/catalogo/{slug}/{entry.pk}/', fetch_redirect_response=False)
                self.assertContains(self.client.get(response.url), 'Cadastro salvo com sucesso.')

    def test_edit_and_unavailability_preserve_id(self):
        self.client.force_login(self.admin)
        for slug, model, data in CASES:
            entry = self.entries[slug]
            count = model.objects.count()
            response = self.client.post(f'/catalogo/{slug}/{entry.pk}/editar/', {
                **data, 'nome': 'Alterado', 'status': 'indisponivel',
            })
            self.assertRedirects(response, f'/catalogo/{slug}/{entry.pk}/')
            entry.refresh_from_db()
            self.assertEqual(entry.nome, 'Alterado')
            self.assertEqual(entry.status, 'indisponivel')
            self.assertEqual(model.objects.count(), count)

    def test_invalid_form_does_not_persist(self):
        self.client.force_login(self.admin)
        invalid = {'servicos': {'status': 'ocupado'}, 'equipamentos': {'nome': ' '},
                   'espacos': {'capacidade_maxima_de_pessoas': 0}}
        for slug, _, data in CASES:
            entry = self.entries[slug]
            old_name = entry.nome
            response = self.client.post(f'/catalogo/{slug}/{entry.pk}/editar/', {**data, **invalid[slug]})
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context['form'].errors)
            entry.refresh_from_db()
            self.assertEqual(entry.nome, old_name)

    def test_catalog_writes_enforce_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.admin)
        client.get('/catalogo/servicos/novo/')
        data = {'nome': 'CSRF', 'status': 'disponivel'}
        self.assertEqual(client.post('/catalogo/servicos/novo/', data).status_code, 403)
        self.assertFalse(Servico.objects.filter(nome='CSRF').exists())
        data['csrfmiddlewaretoken'] = client.cookies['csrftoken'].value
        self.assertEqual(client.post('/catalogo/servicos/novo/', data).status_code, 302)

    def test_list_paginates_25_with_stable_ordering(self):
        Servico.objects.bulk_create([Servico(nome=f'Página {i:02}') for i in range(30)])
        self.client.force_login(self.user)
        response = self.client.get('/catalogo/servicos/')
        self.assertEqual(len(response.context['object_list']), 25)
        self.assertContains(response, '?page=2')
        second = self.client.get('/catalogo/servicos/?page=2')
        expected = list(Servico.objects.order_by('nome', 'pk').values_list('pk', flat=True))
        actual = [entry.pk for entry in response.context['object_list']] + [entry.pk for entry in second.context['object_list']]
        self.assertEqual(actual, expected)

    def test_missing_id_returns_404_for_authenticated_user(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get('/catalogo/espacos/999999/').status_code, 404)

    def test_deactivation_revokes_catalog_access(self):
        self.client.force_login(self.admin)
        self.admin.is_active = False
        self.admin.save(update_fields=['is_active'])
        self.assertRedirects(self.client.get('/catalogo/servicos/'), '/entrar/?next=/catalogo/servicos/', fetch_redirect_response=False)

    def test_home_offers_catalog_without_changing_identity_content(self):
        self.client.force_login(self.user)
        response = self.client.get('/')
        self.assertContains(response, 'leitor')
        self.assertContains(response, '/catalogo/servicos/')
