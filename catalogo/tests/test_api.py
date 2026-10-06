from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client, TestCase

from accounts.tests.test_identity import PASSWORD
from catalogo.models import Espaco, Servico
from catalogo.tests.test_web import CASES


class CatalogApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_user('gestor', password=PASSWORD)
        cls.admin.groups.add(Group.objects.get(name='Administradores'))
        cls.user = get_user_model().objects.create_user('leitor', password=PASSWORD)
        cls.entries = {slug: model.objects.create(**data) for slug, model, data in CASES}

    def test_anonymous_has_no_catalog_access(self):
        for slug, _, data in CASES:
            path = f'/api/v1/{slug}/'
            for response in (self.client.get(path), self.client.post(path, data, content_type='application/json')):
                self.assertEqual(response.status_code, 403)
                self.assertEqual(set(response.json()), {'detail'})

    def test_internal_user_reads_exact_public_fields(self):
        self.client.force_login(self.user)
        for slug, _, data in CASES:
            entry = self.entries[slug]
            response = self.client.get(f'/api/v1/{slug}/{entry.pk}/')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response['Content-Type'], 'application/json')
            self.assertEqual(response.json(), {'id': entry.pk, **data})
            collection = self.client.get(f'/api/v1/{slug}/').json()
            self.assertEqual(set(collection), {'count', 'next', 'previous', 'results'})
            self.assertIn({'id': entry.pk, **data}, collection['results'])

    def test_business_admin_without_staff_creates_and_edits_all_categories(self):
        self.client.force_login(self.admin)
        for slug, model, data in CASES:
            with self.subTest(slug=slug):
                response = self.client.post(f'/api/v1/{slug}/', {**data, 'nome': '  API  '}, content_type='application/json')
                self.assertEqual(response.status_code, 201)
                self.assertEqual(response.json()['nome'], 'API')
                pk = response.json()['id']
                path = f'/api/v1/{slug}/{pk}/'
                response = self.client.patch(path, {'status': 'indisponivel'}, content_type='application/json')
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()['status'], 'indisponivel')
                response = self.client.put(path, {**data, 'nome': 'Editado'}, content_type='application/json')
                self.assertEqual(response.status_code, 200)
                self.assertEqual(model.objects.get(pk=pk).nome, 'Editado')

    def test_regular_and_staff_cannot_create_or_edit(self):
        for staff in (False, True):
            self.user.is_staff = staff
            self.user.save(update_fields=['is_staff'])
            self.client.force_login(self.user)
            for slug, model, data in CASES:
                entry = self.entries[slug]
                count = model.objects.count()
                self.assertEqual(self.client.post(f'/api/v1/{slug}/', data, content_type='application/json').status_code, 403)
                self.assertEqual(self.client.patch(f'/api/v1/{slug}/{entry.pk}/', {'nome': 'Negado'}, content_type='application/json').status_code, 403)
                entry.refresh_from_db()
                self.assertEqual(entry.nome, data['nome'])
                self.assertEqual(model.objects.count(), count)

    def test_api_writes_require_csrf_for_session_authentication(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.admin)
        client.get('/perfil/')
        data = {'nome': 'API com CSRF'}
        path = '/api/v1/servicos/'
        self.assertEqual(client.post(path, data, content_type='application/json').status_code, 403)
        self.assertFalse(Servico.objects.filter(nome=data['nome']).exists())
        response = client.post(path, data, content_type='application/json', HTTP_X_CSRFTOKEN=client.cookies['csrftoken'].value)
        self.assertEqual(response.status_code, 201)

    def test_invalid_patch_does_not_persist_partial_data(self):
        self.client.force_login(self.admin)
        entry = self.entries['espacos']
        for value in (0, -1, 2147483648, 1.5):
            with self.subTest(value=value):
                response = self.client.patch(f'/api/v1/espacos/{entry.pk}/', {
                    'nome': 'Não salvar', 'capacidade_maxima_de_pessoas': value,
                }, content_type='application/json')
                self.assertEqual(response.status_code, 400)
                self.assertIn('capacidade_maxima_de_pessoas', response.json())
                entry.refresh_from_db()
                self.assertEqual(entry.nome, 'Sala')
                self.assertEqual(entry.capacidade_maxima_de_pessoas, 10)

    def test_invalid_name_and_status_are_rejected(self):
        self.client.force_login(self.admin)
        for slug, _, data in CASES:
            for invalid in ({'nome': '   '}, {'nome': 'a' * 151}, {'status': 'incorreto'}):
                response = self.client.post(f'/api/v1/{slug}/', {**data, **invalid}, content_type='application/json')
                self.assertEqual(response.status_code, 400)
        self.assertEqual(self.client.post('/api/v1/servicos/', {'nome': 'Serviço', 'status': 'ocupado'}, content_type='application/json').status_code, 400)

    def test_private_seed_key_is_not_exposed_and_cannot_be_changed(self):
        self.client.force_login(self.admin)
        entry = Servico.objects.get(codigo_inicial='impressao-3d')
        path = f'/api/v1/servicos/{entry.pk}/'
        self.assertNotIn('codigo_inicial', self.client.get(path).json())
        response = self.client.patch(path, {'codigo_inicial': 'outro', 'nome': 'Negado'}, content_type='application/json')
        self.assertEqual(response.status_code, 400)
        entry.refresh_from_db()
        self.assertEqual(entry.codigo_inicial, 'impressao-3d')
        self.assertEqual(entry.nome, 'Impressão 3D')

    def test_put_requires_required_fields(self):
        self.client.force_login(self.admin)
        entry = self.entries['espacos']
        response = self.client.put(f'/api/v1/espacos/{entry.pk}/', {'status': 'indisponivel'}, content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('nome', response.json())

    def test_delete_is_not_supported_and_preserves_records(self):
        self.client.force_login(self.admin)
        for slug, model, _ in CASES:
            entry = self.entries[slug]
            self.assertEqual(self.client.delete(f'/api/v1/{slug}/{entry.pk}/').status_code, 405)
            self.assertTrue(model.objects.filter(pk=entry.pk).exists())

    def test_list_has_stable_pagination_and_order(self):
        Servico.objects.bulk_create([Servico(nome=f'Página {i:02}') for i in range(30)])
        self.client.force_login(self.user)
        first = self.client.get('/api/v1/servicos/').json()
        second = self.client.get('/api/v1/servicos/?page=2').json()
        self.assertEqual(first['count'], 42)
        self.assertEqual(len(first['results']), 25)
        self.assertIn('page=2', first['next'])
        self.assertIsNone(second['next'])
        ids = [item['id'] for item in first['results'] + second['results']]
        self.assertEqual(ids, list(Servico.objects.order_by('nome', 'pk').values_list('pk', flat=True)))

    def test_deactivation_revokes_existing_catalog_session(self):
        self.client.force_login(self.admin)
        self.admin.is_active = False
        self.admin.save(update_fields=['is_active'])
        self.assertEqual(self.client.get('/api/v1/servicos/').status_code, 403)

    def test_logout_revokes_catalog_api_session(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.admin)
        client.get('/perfil/')
        self.assertEqual(client.get('/api/v1/servicos/').status_code, 200)
        client.post('/sair/', {'csrfmiddlewaretoken': client.cookies['csrftoken'].value})
        self.assertEqual(client.get('/api/v1/servicos/').status_code, 403)

    def test_missing_id_returns_404(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get('/api/v1/espacos/999999/').status_code, 404)

    def test_superuser_without_group_can_write(self):
        admin = get_user_model().objects.create_superuser('tecnico', password=PASSWORD)
        self.client.force_login(admin)
        self.assertEqual(self.client.post('/api/v1/espacos/', {
            'nome': 'Superusuário', 'capacidade_maxima_de_pessoas': 1,
        }, content_type='application/json').status_code, 201)
