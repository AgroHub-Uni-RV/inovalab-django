from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase, override_settings
from django.views.defaults import server_error


@override_settings(DEBUG=False)
class ProductErrorPagesTests(TestCase):
    def test_errors_keep_status_and_hide_technical_details(self):
        self.client.force_login(get_user_model().objects.create_user('leitor-erro'))
        forbidden = self.client.get('/usuarios/')
        self.assertContains(forbidden, 'Acesso restrito', status_code=403)
        self.assertNotContains(forbidden, 'Traceback', status_code=403)
        self.assertContains(self.client.get('/pagina-inexistente/'), 'Página não encontrada', status_code=404)
        error = server_error(RequestFactory().get('/'))
        self.assertContains(error, 'Não foi possível carregar esta página', status_code=500)
        self.assertNotContains(error, 'Exception', status_code=500)
