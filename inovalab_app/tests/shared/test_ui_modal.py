from datetime import date, time

from django.test import Client, TestCase

from inovalab_app.catalogo.models import Equipamento
from inovalab_app.conteudo.models import Banner
from inovalab_app.materiais.models import Material
from inovalab_app.tests.conteudo.helpers import BannerFixtures, DATA, image_upload
from inovalab_app.conteudo.services import save_banner
from inovalab_app.agenda.models import AgendaVisita
from inovalab_app.tests.agenda.helpers import make_booking
from inovalab_app.tarefas.services import save_task


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


class ModalConfirmationTests(BannerFixtures, TestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.admin)

    def test_delete_and_restore_return_success_after_effect(self):
        equipment = Equipamento.objects.create(nome='Personalizado')
        banner = save_banner(actor=self.admin, data=DATA, image=image_upload())
        booking = make_booking(actor=self.admin)
        task = save_task(actor=self.admin, data={'agendamento_servico': booking,
                         'responsavel': self.user, 'descricao': 'Excluir no modal'})
        cases = (
            (f'/catalogo/equipamentos/{equipment.pk}/excluir/', {}, equipment, 'excluido_em'),
            (f'/banners/{banner.pk}/excluir/', {'versao': banner.versao}, banner, 'excluido_em'),
            (f'/tarefas/{task.pk}/excluir/', {'versao': task.versao}, task, 'excluida_em'),
        )
        for url, data, model, field in cases:
            with self.subTest(url=url):
                self.assertContains(self.client.get(url), 'data-ui-confirmation')
                self.assertTrue(self.client.post(url, data, HTTP_X_UI_MODAL='1').json()['saved'])
                model.refresh_from_db()
                self.assertIsNotNone(getattr(model, field))
        response = self.client.post('/catalogo/equipamentos/restaurar-padrao/', HTTP_X_UI_MODAL='1')
        self.assertTrue(response.json()['saved'])
        equipment.refresh_from_db()
        self.assertIsNotNone(equipment.excluido_em)

    def test_review_realization_and_cancellation_preserve_versions(self):
        visit = AgendaVisita.objects.create(quantidade_pessoas=2, data=date(2026, 10, 8),
                    hora_inicio=time(9), hora_termino=time(10), criado_por=self.admin, situacao='pendente')
        review = f'/agenda/visita/{visit.pk}/avaliar/'
        response = self.client.post(review, {'versao': 1, 'decisao': 'aprovar'}, HTTP_X_UI_MODAL='1')
        self.assertTrue(response.json()['saved'])
        stale = self.client.post(review, {'versao': 1, 'decisao': 'rejeitar'}, HTTP_X_UI_MODAL='1')
        self.assertContains(stale, 'data-ui-modal-page', status_code=409)
        realization = f'/agenda/visita/{visit.pk}/realizar/'
        self.assertTrue(self.client.post(realization, {'versao': 2}, HTTP_X_UI_MODAL='1').json()['saved'])
        visit.refresh_from_db()
        self.assertIsNotNone(visit.realizada_em)
        cancel = f'/agenda/visita/{visit.pk}/cancelar/'
        self.assertContains(self.client.get(cancel), 'data-ui-confirmation')
        self.assertTrue(self.client.post(cancel, {'versao': visit.versao}, HTTP_X_UI_MODAL='1').json()['saved'])
        visit.refresh_from_db()
        self.assertIsNotNone(visit.cancelado_em)

    def test_personal_cancel_works_in_modal_for_active_external_owner(self):
        from django.contrib.auth import get_user_model
        owner = get_user_model().objects.create_user('titular-modal')
        visit = AgendaVisita.objects.create(quantidade_pessoas=2, data=date(2099, 10, 8),
                    hora_inicio=time(9), hora_termino=time(10), criado_por=owner, situacao='pendente')
        self.client.force_login(owner)
        url = f'/agenda/meus/visita/{visit.pk}/cancelar/'
        self.assertContains(self.client.get(url), 'data-ui-confirmation')
        response = self.client.post(url, {'versao': 1}, HTTP_X_UI_MODAL='1')
        self.assertEqual(response.json(), {'saved': True, 'redirect_url': '/agenda/meus/'})
