from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from inovalab_app.agenda.models import AgendaEquipamento, AgendaVisita
from inovalab_app.catalogo.models import Equipamento
from inovalab_app.tarefas.models import Tarefa
from inovalab_app.tests.agenda.helpers import make_booking
from inovalab_app.tests.agenda.test_execution import NOW


class ManagementExecutionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_superuser('gerencia-admin')
        cls.owner = get_user_model().objects.create_user('gerencia-titular', is_staff=True)

    def setUp(self):
        self.client.force_login(self.admin)
        clock = patch('inovalab_app.agenda.views.timezone.now', return_value=NOW)
        clock.start()
        self.addCleanup(clock.stop)

    def visit(self, start, end, **fields):
        return AgendaVisita.objects.create(criado_por=self.owner, quantidade_pessoas=3,
            data=NOW.date(), hora_inicio=start, hora_termino=end, **fields)

    def groups(self, response):
        return [*response.context['execution_groups'], response.context['execution_attention'],
                response.context['historical_equipment']]

    def test_confirmed_groups_partition_all_categories(self):
        services = [make_booking(actor=self.owner, prazo=NOW, titulo=f'Serviço {i}') for i in range(3)]
        for index, booking in enumerate(services):
            Tarefa.objects.create(agendamento_servico=booking, responsavel=self.owner, descricao='Executar',
                status='concluido' if index == 2 else 'demanda',
                inicio=NOW-timedelta(hours=1) if index else None,
                conclusao=NOW if index == 2 else None)
        visits = [self.visit(NOW.replace(hour=13).time(), NOW.replace(hour=14).time()),
                  self.visit(NOW.replace(hour=11).time(), NOW.replace(hour=13).time()),
                  self.visit(NOW.replace(hour=9).time(), NOW.replace(hour=10).time(), realizada_em=NOW),
                  self.visit(NOW.replace(hour=8).time(), NOW.replace(hour=9).time())]
        equipment = AgendaEquipamento.objects.create(criado_por=self.owner,
            equipamento=Equipamento.objects.create(nome='Histórico'),
            inicio=NOW.replace(hour=9), fim=NOW.replace(hour=10))
        make_booking(actor=self.owner, situacao='pendente')
        response = self.client.get('/agenda/solicitacoes/', {'status': 'confirmada'})
        self.assertContains(response, 'Gerenciamento de agendamentos')
        groups = self.groups(response)
        self.assertEqual([group['count'] for group in groups], [2, 2, 2, 1, 1])
        identities = [(row.categoria, row.pk) for group in groups for row in group['bookings']]
        self.assertEqual(len(identities), len(set(identities)))
        self.assertEqual(set(identities), {(row.categoria, row.pk) for row in [*services, *visits, equipment]})
        self.assertContains(response, 'Marcar como realizada', count=2)
        self.assertContains(response, 'Aguardando encerramento')
        self.assertContains(response, 'Equipamentos históricos')

    def test_total_counts_are_independent_of_current_page(self):
        for index in range(27):
            make_booking(actor=self.owner, titulo=f'Paginação {index}', prazo=NOW)
        response = self.client.get('/agenda/solicitacoes/', {'status': 'confirmada', 'page': 2})
        self.assertEqual(response.context['paginator'].count, 27)
        self.assertEqual(len(response.context['object_list']), 2)
        self.assertEqual(sum(group['count'] for group in self.groups(response)), 27)
        self.assertContains(response, 'Nenhum agendamento neste grupo.', count=2)

    def test_all_tab_keeps_approval_groups_and_actions(self):
        pending = make_booking(actor=self.owner, situacao='pendente')
        make_booking(actor=self.owner, situacao='rejeitado')
        make_booking(actor=self.owner, cancelado_em=NOW)
        self.visit(NOW.replace(hour=11).time(), NOW.replace(hour=13).time())
        response = self.client.get('/agenda/solicitacoes/')
        self.assertContains(response, f'/tarefas/confirmar-servico/{pending.pk}/')
        self.assertContains(response, 'Recusar', count=1)
        self.assertContains(response, '>Cancelar</button>', count=1)
        self.assertContains(response, 'Marcar como realizada', count=1)
        self.assertNotContains(response, 'execution-board')
        self.assertEqual([column['count'] for column in response.context['columns']], [1, 1, 1, 1])
        for status in ('pendente', 'cancelada', 'recusada'):
            result = self.client.get('/agenda/solicitacoes/', {'status': status})
            self.assertEqual(len(result.context['object_list']), 1)
            self.assertNotContains(result, 'Marcar como realizada')

    def test_execution_filter_combines_with_tabs_and_clear_resets_everything(self):
        target = make_booking(actor=self.owner, prazo=NOW-timedelta(hours=1), titulo='Busca especial')
        make_booking(actor=self.owner, prazo=NOW-timedelta(hours=1), titulo='Busca especial', situacao='pendente')
        query = {'q': 'Busca especial', 'mes': '2026-10', 'status': 'confirmada', 'execucao': 'atrasado'}
        response = self.client.get('/agenda/solicitacoes/', query)
        self.assertEqual([row.pk for row in response.context['object_list']], [target.pk])
        self.assertEqual(response.context['selected_execution'], 'atrasado')
        self.assertContains(response, 'execucao=atrasado')
        self.assertContains(response, 'data-clear-filters href="/agenda/solicitacoes/"')
        self.assertEqual(self.client.get('/agenda/solicitacoes/', {**query, 'status': 'pendente'}).context['paginator'].count, 0)
        self.assertEqual(self.client.get('/agenda/solicitacoes/', {'execucao': 'inventado'}).status_code, 400)
        clear = self.client.get('/agenda/solicitacoes/')
        self.assertEqual((clear.context['selected_status'], clear.context['selected_execution'], clear.context['page_obj'].number), ('', '', 1))
