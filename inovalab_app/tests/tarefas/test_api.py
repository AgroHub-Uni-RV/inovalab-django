from inovalab_app.tests.agenda.helpers import make_service, make_booking
from django.test import Client, TestCase

from inovalab_app.tarefas.models import Tarefa
from inovalab_app.tarefas.services import save_task, transition_task
from inovalab_app.tests.tarefas.helpers import TaskFixtures


class TaskApiTests(TaskFixtures, TestCase):
    def test_anonymous_has_no_access(self):
        for path in ('/api/v1/tarefas/', f'/api/v1/tarefas/{self.mine.pk}/', '/api/v1/tarefas/responsaveis/'):
            self.assertEqual(self.client.get(path).status_code, 403)

    def test_owner_list_and_detail_never_disclose_foreign_tasks(self):
        self.client.force_login(self.owner)
        result = self.client.get('/api/v1/tarefas/').json()
        self.assertEqual(set(result), {'count', 'next', 'previous', 'results'})
        self.assertEqual(result['count'], 1)
        entry = result['results'][0]
        self.assertEqual(entry['id'], self.mine.pk)
        self.assertEqual(entry['status'], 'demanda')
        self.assertEqual(entry['acoes_permitidas'], ['iniciar'])
        self.assertEqual(set(entry), {'id', 'agendamento_servico', 'equipamento', 'material_gasto', 'quantidade_material_gasto', 'servico', 'servico_nome', 'descricao', 'responsavel', 'responsavel_nome',
                                      'responsaveis', 'equipamentos', 'materiais_gastos',
                                      'status', 'inicio', 'prazo', 'conclusao', 'versao', 'acoes_permitidas'})
        foreign = f'/api/v1/tarefas/{self.theirs.pk}/'
        for response in (self.client.get(foreign), self.client.patch(foreign, {'descricao': 'Negada', 'versao': 1},
                          content_type='application/json'), self.client.get(foreign + 'historico/'),
                         self.client.post(foreign + 'transicoes/', {'acao': 'iniciar', 'versao': 1}, content_type='application/json')):
            self.assertEqual(response.status_code, 404)
            self.assertNotContains(response, self.theirs.descricao, status_code=404)

    def test_admin_creates_and_edits_metadata_without_staff(self):
        self.client.force_login(self.admin)
        response = self.client.post('/api/v1/tarefas/', self.payload(), content_type='application/json')
        self.assertEqual(response.status_code, 201)
        task_id = response.json()['id']
        self.assertEqual(response.json()['status'], 'demanda')
        response = self.client.patch(f'/api/v1/tarefas/{task_id}/', {'descricao': 'Editada', 'versao': 1}, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual((response.json()['descricao'], response.json()['versao']), ('Editada', 2))
        self.assertIn(response.json()['prazo'][-6:], ('-03:00', '+00:00'))

    def test_regular_and_staff_cannot_administer_own_task(self):
        for actor, task in ((self.owner, self.mine), (self.other, self.theirs)):
            self.client.force_login(actor)
            self.assertEqual(self.client.post('/api/v1/tarefas/', self.payload(), content_type='application/json').status_code, 403)
            path = f'/api/v1/tarefas/{task.pk}/'
            self.assertEqual(self.client.patch(path, {'descricao': 'Negada', 'versao': 1}, content_type='application/json').status_code, 403)
            self.assertEqual(self.client.delete(path, {'versao': 1}, content_type='application/json').status_code, 403)
            task.refresh_from_db()
            self.assertEqual(task.versao, 1)

    def test_owner_transitions_and_admin_evaluation_share_domain_rules(self):
        self.client.force_login(self.owner)
        path = f'/api/v1/tarefas/{self.mine.pk}/transicoes/'
        for action, version, status in (('iniciar', 1, 'criacao'), ('enviar', 2, 'avaliacao')):
            response = self.client.post(path, {'acao': action, 'versao': version}, content_type='application/json')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()['status'], status)
            self.assertIsNotNone(response.json()['inicio'])
        for action in ('aprovar', 'recusar', 'reabrir'):
            self.assertEqual(self.client.post(path, {'acao': action, 'versao': 3}, content_type='application/json').status_code, 403)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.post(path, {'acao': 'aprovar', 'versao': 3}, content_type='application/json').json()['status'], 'concluido')
        response = self.client.post(path, {'acao': 'reabrir', 'versao': 4}, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'criacao')
        self.assertIsNone(response.json()['conclusao'])

    def test_protected_and_unknown_fields_rejected_without_partial_save(self):
        self.client.force_login(self.admin)
        for field, value in (('status', 'concluido'), ('inicio', '2026-01-01T10:00:00Z'), ('conclusao', None),
                             ('excluida_em', None), ('id', 999), ('desconhecido', 1)):
            response = self.client.patch(f'/api/v1/tarefas/{self.mine.pk}/',
                {'descricao': 'Não salvar', 'versao': 1, field: value}, content_type='application/json')
            self.assertEqual(response.status_code, 400)
            self.assertIn(field, response.json())
        self.mine.refresh_from_db()
        self.assertEqual(self.mine.descricao, 'Protótipo privado de Ana')
        self.assertEqual(self.mine.eventos.count(), 1)

    def test_transition_rejects_metadata_extra_fields_and_invalid_payload(self):
        self.client.force_login(self.owner)
        path = f'/api/v1/tarefas/{self.mine.pk}/transicoes/'
        for payload in ({'acao': 'iniciar', 'versao': 1, 'responsavel': self.other.pk},
                        {'acao': 'iniciar', 'versao': True}, {'acao': 'iniciar', 'versao': 1.5},
                        {'acao': 'iniciar', 'versao': 0}, {'acao': 'iniciar'}, {'acao': 'aprovarXXX', 'versao': 1}, []):
            with self.subTest(payload=payload):
                self.assertEqual(self.client.post(path, payload, content_type='application/json').status_code, 400)
        self.mine.refresh_from_db()
        self.assertEqual((self.mine.status, self.mine.versao, self.mine.eventos.count()), ('demanda', 1, 1))

    def test_old_versions_return_409_on_all_write_operations(self):
        self.client.force_login(self.admin)
        path = f'/api/v1/tarefas/{self.mine.pk}/'
        self.assertEqual(self.client.patch(path, {'descricao': 'Atualizada', 'versao': 1}, content_type='application/json').status_code, 200)
        for response in (self.client.patch(path, {'descricao': 'Antiga', 'versao': 1}, content_type='application/json'),
                         self.client.post(path + 'transicoes/', {'acao': 'iniciar', 'versao': 1}, content_type='application/json'),
                         self.client.delete(path, {'versao': 1}, content_type='application/json')):
            self.assertEqual(response.status_code, 409)
            self.assertEqual(response.json()['code'], 'versao_desatualizada')

    def test_api_history_is_scoped_and_includes_real_changes(self):
        task = transition_task(actor=self.owner, task_id=self.mine.pk, action='iniciar', expected_version=1)
        self.client.force_login(self.owner)
        response = self.client.get(f'/api/v1/tarefas/{task.pk}/historico/')
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result['count'], 2)
        event = result['results'][0]
        self.assertEqual((event['acao'], event['ator_nome'], event['status_novo']), ('iniciar', 'ana', 'criacao'))
        self.assertEqual(event['alteracoes']['status'], {'anterior': 'demanda', 'novo': 'criacao'})

    def test_reassignment_and_soft_delete_revoke_detail_history_and_counts(self):
        task = save_task(actor=self.admin, task_id=self.mine.pk, expected_version=1, data={'responsavel': self.other})
        self.client.force_login(self.owner)
        path = f'/api/v1/tarefas/{task.pk}/'
        self.assertEqual(self.client.get('/api/v1/tarefas/').json()['count'], 0)
        self.assertEqual(self.client.get(path).status_code, 404)
        self.assertEqual(self.client.get(path + 'historico/').status_code, 404)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.delete(path, {'versao': 2}, content_type='application/json').status_code, 204)
        self.assertEqual(self.client.get(path).status_code, 404)
        self.assertEqual(self.client.get(path + 'historico/').status_code, 404)
        self.assertEqual(Tarefa.objects.get(pk=task.pk).eventos.count(), 3)

    def test_responsible_options_are_admin_only_active_and_paginated(self):
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get('/api/v1/tarefas/responsaveis/').status_code, 403)
        self.other.is_active = False
        self.other.save()
        self.client.force_login(self.admin)
        result = self.client.get('/api/v1/tarefas/responsaveis/').json()
        self.assertEqual({user['id'] for user in result['results']}, {self.admin.pk, self.owner.pk})
        self.assertEqual(set(result['results'][0]), {'id', 'username', 'nome'})

    def test_writes_require_csrf_and_inactive_session_is_revoked(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.admin)
        client.get('/perfil/')
        path = f'/api/v1/tarefas/{self.mine.pk}/transicoes/'
        data = {'acao': 'iniciar', 'versao': 1}
        self.assertEqual(client.post(path, data, content_type='application/json').status_code, 403)
        self.assertEqual(client.post(path, data, content_type='application/json',
                                    HTTP_X_CSRFTOKEN=client.cookies['csrftoken'].value).status_code, 200)
        self.admin.is_active = False
        self.admin.save()
        self.assertEqual(client.get('/api/v1/tarefas/').status_code, 403)

    def test_pagination_never_widens_owner_scope(self):
        for index in range(26):
            save_task(actor=self.admin, data={'agendamento_servico': self.booking, 'responsavel': self.owner, 'descricao': f'Página {index}'})
        self.client.force_login(self.owner)
        first = self.client.get('/api/v1/tarefas/').json()
        second = self.client.get('/api/v1/tarefas/?page=2').json()
        self.assertEqual((first['count'], len(first['results']), len(second['results'])), (27, 25, 2))
        self.assertTrue(all(item['responsavel'] == self.owner.pk for item in first['results'] + second['results']))

    def test_required_description_and_invalid_references_reject_create(self):
        self.client.force_login(self.admin)
        for data in (self.payload(descricao='   '), self.payload(servico=999999), self.payload(responsavel=999999), self.payload(status='demanda')):
            self.assertEqual(self.client.post('/api/v1/tarefas/', data, content_type='application/json').status_code, 400)
        self.assertEqual(Tarefa.objects.count(), 2)
