from django.test import TestCase
from inovalab_app.tarefas.models import Tarefa
from inovalab_app.tests.tarefas.test_multiple_links import MultipleLinksFixtures


class MultipleTaskLinksWebTests(MultipleLinksFixtures, TestCase):
    def form_payload(self, **overrides):
        return {
            'agendamento_servico': self.booking.pk, 'descricao': 'Tarefa plural web',
            'responsaveis': [self.owner.pk, self.other.pk],
            'equipamentos': [item.pk for item in self.equipment],
            'materiais-TOTAL_FORMS': '2', 'materiais-INITIAL_FORMS': '0',
            'materiais-0-material': self.materials[0].pk, 'materiais-0-quantidade': '30 g',
            'materiais-1-material': self.materials[1].pk, 'materiais-1-quantidade': '2 unidades',
            **overrides,
        }

    def test_web_creates_all_links_and_displays_every_resource(self):
        self.client.force_login(self.admin)
        response = self.client.post('/tarefas/nova/', self.form_payload())
        self.assertEqual(response.status_code, 302, response.context['form'].errors if response.status_code == 200 else '')
        task = Tarefa.objects.get(descricao='Tarefa plural web')
        self.assertEqual((task.responsaveis.count(), task.equipamentos.count(), task.materiais_gastos.count()), (2, 2, 2))
        detail = self.client.get(response.url)
        for text in (self.owner.username, self.other.username, self.equipment[1].nome, self.materials[1].nome, '30 g', '2 unidades'):
            self.assertContains(detail, text)

    def test_web_invalid_material_or_empty_team_cannot_create_task(self):
        self.client.force_login(self.admin)
        for override in ({'responsaveis': []}, {'materiais-1-material': self.materials[0].pk},
                         {'materiais-1-material': '', 'materiais-1-quantidade': '10 g'}):
            response = self.client.post('/tarefas/nova/', self.form_payload(**override))
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, 'Confira os erros')
        self.assertFalse(Tarefa.objects.filter(descricao='Tarefa plural web').exists())

    def test_add_material_without_javascript_keeps_draft_and_does_not_save(self):
        self.client.force_login(self.admin)
        response = self.client.post('/tarefas/nova/', self.form_payload(adicionar_material='1'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="materiais-2-material"')
        self.assertContains(response, '30 g')
        self.assertFalse(Tarefa.objects.filter(descricao='Tarefa plural web').exists())

    def test_api_plural_create_partial_update_and_secondary_owner_scope(self):
        self.client.force_login(self.admin)
        response = self.client.post('/api/v1/tarefas/', {
            'agendamento_servico': self.booking.pk, 'descricao': 'Tarefa plural API',
            'responsaveis': [self.owner.pk, self.other.pk], 'equipamentos': [item.pk for item in self.equipment],
            'materiais_gastos': [{'material': self.materials[0].pk, 'quantidade': '20 g'},
                                {'material': self.materials[1].pk, 'quantidade': 'meia bobina'}],
        }, content_type='application/json')
        self.assertEqual(response.status_code, 201, response.content)
        task = response.json()
        self.assertEqual(task['responsaveis'], [self.owner.pk, self.other.pk])
        self.assertEqual([item['quantidade'] for item in task['materiais_gastos']], ['20 g', 'meia bobina'])
        url = f'/api/v1/tarefas/{task["id"]}/'
        response = self.client.patch(url, {'descricao': 'Só descrição', 'versao': 1}, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['responsaveis'], task['responsaveis'])
        self.assertEqual(response.json()['materiais_gastos'], task['materiais_gastos'])
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(self.client.post(url+'transicoes/', {'status': 'criacao', 'versao': 2},
                                         content_type='application/json').status_code, 200)

    def test_api_rejects_alias_conflicts_duplicate_material_and_invalid_quantity(self):
        self.client.force_login(self.admin)
        for fields in ({'responsavel': self.owner.pk, 'responsaveis': [self.other.pk]},
                       {'materiais_gastos': [{'material': self.materials[0].pk}, {'material': self.materials[0].pk}]},
                       {'materiais_gastos': [{'material': self.materials[0].pk, 'quantidade': 'x'*151}]}):
            response = self.client.post('/api/v1/tarefas/', {
                'agendamento_servico': self.booking.pk, 'descricao': 'Inválida API',
                'responsaveis': [self.owner.pk], **fields,
            }, content_type='application/json')
            self.assertEqual(response.status_code, 400)
        self.assertFalse(Tarefa.objects.filter(descricao='Inválida API').exists())

    def test_search_secondary_responsible_returns_single_task_with_unique_counts(self):
        task = self.create_multiple()
        self.client.force_login(self.admin)
        response = self.client.get('/tarefas/', {'q': self.other.username})
        self.assertIn(task.pk, [item.pk for item in response.context['object_list']])
        self.client.force_login(self.owner)
        response = self.client.get('/tarefas/', {'q': 'Tarefa da equipe'})
        self.assertEqual((response.context['paginator'].count, response.context['stat_counts']['demanda']), (1, 1))
