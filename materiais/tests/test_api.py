import json

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client, TestCase

from integracoes.services import create_client
from materiais.models import Material
from materiais.services import save_material
from materiais.tests.test_services import DATA


class MaterialApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_user('api-gestor-material')
        cls.admin.groups.add(Group.objects.get(name='Administradores'))
        cls.user = get_user_model().objects.create_user('api-leitor-material', is_staff=True)
        cls.material = save_material(actor=cls.admin, data=DATA)

    def setUp(self):
        self.path = f'/api/v1/materiais/{self.material.pk}/'

    def test_anonymous_and_external_token_do_not_authenticate(self):
        _, token = create_client(actor=self.admin, name='Consumidor de teste')
        for headers in ({}, {'HTTP_AUTHORIZATION': f'Bearer {token}'}):
            self.assertEqual(self.client.get('/api/v1/materiais/', **headers).status_code, 403)
            self.assertEqual(self.client.post('/api/v1/materiais/', DATA, content_type='application/json',
                                              **headers).status_code, 403)

    def test_reader_receives_public_contract_with_decimal_string(self):
        self.client.force_login(self.user)
        response = self.client.get(self.path)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'id': self.material.pk, **DATA, 'versao': 1})
        self.assertEqual(response['Content-Type'], 'application/json')

    def test_regular_and_staff_cannot_write(self):
        for staff in (False, True):
            self.user.is_staff = staff
            self.user.save(update_fields=['is_staff'])
            self.client.force_login(self.user)
            self.assertEqual(self.client.post('/api/v1/materiais/', DATA,
                                              content_type='application/json').status_code, 403)
            self.assertEqual(self.client.patch(self.path, {'versao': 1, 'quantidade': '0'},
                                               content_type='application/json').status_code, 403)
        self.material.refresh_from_db()
        self.assertEqual(self.material.versao, 1)

    def test_admin_without_staff_creates_and_corrects(self):
        self.assertFalse(self.admin.is_staff)
        self.client.force_login(self.admin)
        created = self.client.post('/api/v1/materiais/', {**DATA, 'quantidade': 1.125},
                                   content_type='application/json')
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.json()['quantidade'], '1.125')
        changed = self.client.patch(self.path, {'quantidade': '8', 'versao': 1},
                                    content_type='application/json')
        self.assertEqual(changed.status_code, 200)
        self.assertEqual((changed.json()['quantidade'], changed.json()['versao']), ('8.000', 2))

    def test_stale_edit_returns_machine_code_and_preserves_winner(self):
        self.client.force_login(self.admin)
        self.client.patch(self.path, {'nome': 'Vencedor', 'versao': 1}, content_type='application/json')
        response = self.client.patch(self.path, {'nome': 'Perdedor', 'quantidade': '0', 'versao': 1},
                                      content_type='application/json')
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()['code'], 'versao_desatualizada')
        self.material.refresh_from_db()
        self.assertEqual((self.material.nome, str(self.material.quantidade), self.material.versao),
                         ('Vencedor', '10.000', 2))

    def test_upper_decimal_limit_roundtrips_exactly(self):
        self.client.force_login(self.admin)
        response = self.client.post('/api/v1/materiais/', {**DATA, 'quantidade': '999999999.999'},
                                   content_type='application/json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['quantidade'], '999999999.999')
        material = Material.objects.get(pk=response.json()['id'])
        self.assertEqual(str(material.quantidade), '999999999.999')

    def test_raw_json_numbers_keep_precision_until_validation(self):
        self.client.force_login(self.admin)
        for number in ('0.10000000000000001', '999999999.99900001', '123456789.1234'):
            with self.subTest(number=number):
                raw = json.dumps({**DATA, 'quantidade': '__numeric__'}).replace('"__numeric__"', number)
                response = self.client.post('/api/v1/materiais/', raw, content_type='application/json')
                self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(Material.objects.count(), 1)

    def test_invalid_raw_number_patch_preserves_material(self):
        self.client.force_login(self.admin)
        raw = '{"nome":"Não salvar","quantidade":999999999.99900001,"versao":1}'
        response = self.client.patch(self.path, raw, content_type='application/json')
        self.assertEqual(response.status_code, 400, response.content)
        self.material.refresh_from_db()
        self.assertEqual((self.material.nome, str(self.material.quantidade), self.material.versao),
                         ('Filamento', '10.000', 1))

    def test_version_is_required_strict_and_server_assigned_at_creation(self):
        self.client.force_login(self.admin)
        for version in (None, True, '1', 1.0, 0, -1, 9223372036854775807):
            body = {} if version is None else {'versao': version}
            response = self.client.patch(self.path, {**body, 'nome': 'Inválido'},
                                          content_type='application/json')
            self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(self.client.post('/api/v1/materiais/', {**DATA, 'versao': 1},
                                          content_type='application/json').status_code, 400)

    def test_invalid_quantity_never_rounds_or_saves_partial_fields(self):
        self.client.force_login(self.admin)
        for value in ('-1', '0.0001', '1000000000', 'NaN', 'Infinity', '1,5', True, None):
            with self.subTest(value=value):
                response = self.client.patch(self.path, {'quantidade': value, 'nome': 'Não salvar', 'versao': 1},
                                              content_type='application/json')
                self.assertEqual(response.status_code, 400, response.content)
        self.material.refresh_from_db()
        self.assertEqual((self.material.nome, str(self.material.quantidade), self.material.versao),
                         ('Filamento', '10.000', 1))

    def test_unknown_readonly_and_non_object_json_are_rejected(self):
        self.client.force_login(self.admin)
        for data in ([DATA], {'id': 12, **DATA}, {'extra': True, **DATA}):
            response = self.client.post('/api/v1/materiais/', data, content_type='application/json')
            self.assertEqual(response.status_code, 400)
        self.assertEqual(Material.objects.count(), 1)

    def test_required_text_and_status_cannot_be_empty_or_invalid(self):
        self.client.force_login(self.admin)
        for field, value in (('nome', ' '), ('categoria', ''), ('unidade', ''), ('fonte', ''),
                             ('status', 'devolvido'), ('fonte', 5)):
            response = self.client.post('/api/v1/materiais/', {**DATA, **{field: value}},
                                        content_type='application/json')
            self.assertEqual(response.status_code, 400)

    def test_put_requires_complete_material_and_version(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.put(self.path, {'quantidade': '8', 'versao': 1},
                                         content_type='application/json').status_code, 400)
        response = self.client.put(self.path, {**DATA, 'quantidade': '0', 'status': 'indisponivel', 'versao': 1},
                                    content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual((response.json()['quantidade'], response.json()['status']), ('0.000', 'indisponivel'))

    def test_pagination_is_stable_and_includes_unavailable(self):
        Material.objects.bulk_create([Material(**{**DATA, 'nome': f'Material {i:02}', 'status': 'indisponivel'})
                                      for i in range(28)])
        self.client.force_login(self.user)
        first = self.client.get('/api/v1/materiais/').json()
        second = self.client.get('/api/v1/materiais/?page=2').json()
        self.assertEqual((first['count'], len(first['results']), len(second['results'])), (29, 25, 4))
        self.assertIsNotNone(first['next'])
        self.assertIsNone(second['next'])
        ids = [item['id'] for item in first['results'] + second['results']]
        self.assertEqual(len(set(ids)), 29)

    def test_session_csrf_enforced_and_json_only(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.admin)
        client.get('/')
        self.assertEqual(client.post('/api/v1/materiais/', DATA,
                                     content_type='application/json').status_code, 403)
        token = client.cookies['csrftoken'].value
        self.assertEqual(client.post('/api/v1/materiais/', DATA,
                                     HTTP_X_CSRFTOKEN=token).status_code, 415)
        self.assertEqual(client.post('/api/v1/materiais/', DATA, content_type='application/json',
                                     HTTP_X_CSRFTOKEN=token).status_code, 201)

    def test_delete_is_unsupported_and_missing_id_is_404(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.delete(self.path).status_code, 405)
        self.assertTrue(Material.objects.filter(pk=self.material.pk).exists())
        self.assertEqual(self.client.get('/api/v1/materiais/999999/').status_code, 404)

    def test_deactivating_account_revokes_read_and_write(self):
        self.client.force_login(self.admin)
        self.admin.is_active = False
        self.admin.save(update_fields=['is_active'])
        self.assertEqual(self.client.get(self.path).status_code, 403)
        self.assertEqual(self.client.patch(self.path, {'versao': 1, 'nome': 'Negado'},
                                          content_type='application/json').status_code, 403)
