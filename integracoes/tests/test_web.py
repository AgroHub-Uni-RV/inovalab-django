from datetime import datetime

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client, TestCase

from catalogo.models import Servico
from integracoes.credentials import CredentialRejected, authenticate_token
from integracoes.models import ClienteIntegracao
from integracoes.services import create_client, receive_booking, update_client


class IntegrationWebTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_user('gestor')
        cls.admin.groups.add(Group.objects.get(name='Administradores'))
        cls.user = get_user_model().objects.create_user('staff', is_staff=True)
        cls.service = Servico.objects.first()

    def setUp(self):
        self.client.force_login(self.admin)
        self.integration, self.token = create_client(actor=self.admin, name='AgroHub')

    def test_anonymous_redirect_and_all_non_admin_routes_are_denied(self):
        urls = ['/integracoes/', '/integracoes/novo/', f'/integracoes/{self.integration.pk}/',
                f'/integracoes/{self.integration.pk}/editar/', f'/integracoes/{self.integration.pk}/credencial/',
                f'/integracoes/{self.integration.pk}/pedidos/']
        self.client.logout()
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.user)
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.post('/integracoes/novo/', {'nome': 'Não criar'}).status_code, 403)

    def test_create_displays_secret_once_with_no_store_and_next_pages_never_expose_it(self):
        response = self.client.post('/integracoes/novo/', {'nome': 'Novo sistema'})
        self.assertEqual(response.status_code, 200)
        token = response.context['token']
        created = ClienteIntegracao.objects.get(nome='Novo sistema')
        self.assertContains(response, token)
        self.assertEqual(response['Cache-Control'], 'no-store, private')
        self.assertEqual(response['Referrer-Policy'], 'no-referrer')
        self.assertEqual(authenticate_token(token).cliente_id, created.pk)
        self.assertNotEqual(created.token_digest, token)
        for url in ('/integracoes/', f'/integracoes/{created.pk}/', f'/integracoes/{created.pk}/editar/'):
            self.assertNotContains(self.client.get(url), token)
            self.assertNotContains(self.client.get(url), created.token_digest)

    def test_rotation_confirmation_get_is_safe_post_requires_version_and_revokes_previous(self):
        url = f'/integracoes/{self.integration.pk}/credencial/'
        self.assertContains(self.client.get(url), 'Gerar nova credencial')
        self.assertEqual(authenticate_token(self.token).cliente_id, self.integration.pk)
        response = self.client.post(url, {'versao': 1})
        token = response.context['token']
        self.assertEqual(response['Cache-Control'], 'no-store, private')
        with self.assertRaises(CredentialRejected):
            authenticate_token(self.token)
        self.assertEqual(authenticate_token(token).cliente_id, self.integration.pk)
        self.assertEqual(self.client.post(url, {'versao': 1}).status_code, 409)
        self.assertEqual(self.client.post(url, {}).status_code, 400)

    def test_edit_deactivation_invalidates_secret_and_stale_edit_does_not_reactivate(self):
        url = f'/integracoes/{self.integration.pk}/editar/'
        response = self.client.post(url, {'nome': 'AgroHub', 'versao': 1})
        self.assertRedirects(response, f'/integracoes/{self.integration.pk}/')
        with self.assertRaises(CredentialRejected):
            authenticate_token(self.token)
        self.assertEqual(self.client.post(url, {'nome': 'AgroHub', 'ativo': 'on', 'versao': 1}).status_code, 409)
        self.integration.refresh_from_db()
        self.assertFalse(self.integration.ativo)

    def test_unknown_fields_duplicate_name_and_invalid_version_do_not_persist(self):
        self.assertEqual(self.client.post('/integracoes/novo/', {'nome': 'AgroHub'}).status_code, 200)
        self.assertEqual(self.client.post('/integracoes/novo/', {'nome': 'Outro', 'token_digest': 'x'}).status_code, 200)
        self.assertEqual(ClienteIntegracao.objects.count(), 1)
        url = f'/integracoes/{self.integration.pk}/editar/'
        for fields in ({'versao': ''}, {'token_digest': 'x'}):
            self.assertEqual(self.client.post(url, {'nome': 'Outro', 'ativo': 'on', 'versao': 1, **fields}).status_code, 200)
        self.integration.refresh_from_db()
        self.assertEqual((self.integration.nome, self.integration.versao), ('AgroHub', 1))

    def test_csrf_required_for_create_update_and_rotation(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.admin)
        for url, data in (('/integracoes/novo/', {'nome': 'Novo'}), (f'/integracoes/{self.integration.pk}/editar/', {'nome': 'Outro', 'versao': 1}),
                          (f'/integracoes/{self.integration.pk}/credencial/', {'versao': 1})):
            self.assertEqual(client.post(url, data).status_code, 403)

    def test_external_origin_requester_and_request_id_are_visible_only_to_admin(self):
        booking, receipt, _ = receive_booking(principal=authenticate_token(self.token), data={
            'categoria': 'servico', 'objeto': self.service.pk, 'requerente': 'Ana', 'requerente_id': 'pessoa-45',
            'id_externo': 'pedido-001', 'motivo': 'Protótipo', 'inicio': datetime.fromisoformat('2026-11-01T14:00:00-03:00'),
            'fim': datetime.fromisoformat('2026-11-01T15:00:00-03:00')})
        for url in (f'/agenda/{booking.categoria}/{booking.pk}/', f'/integracoes/{self.integration.pk}/pedidos/'):
            response = self.client.get(url)
            for text in ('AgroHub', 'pedido-001', 'pessoa-45'):
                self.assertContains(response, text)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(f'/integracoes/{self.integration.pk}/pedidos/').status_code, 403)

    def test_client_list_pagination_and_navigation_respects_role(self):
        for index in range(25):
            create_client(actor=self.admin, name=f'Sistema {index}')
        response = self.client.get('/integracoes/')
        self.assertEqual((response.context['paginator'].count, len(response.context['object_list'])), (26, 25))
        self.assertContains(response, 'Próxima')
        self.assertEqual(len(self.client.get('/integracoes/', {'page': 2}).context['object_list']), 1)
        self.assertContains(self.client.get('/perfil/'), '/integracoes/')
        self.client.force_login(self.user)
        self.assertNotContains(self.client.get('/perfil/'), '/integracoes/')
