from inovalab_app.tests.agenda.helpers import make_service, make_booking
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Group
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models.deletion import ProtectedError
from django.http import Http404
from django.test import TestCase
from django.utils import timezone

from inovalab_app.catalogo.models import Servico
from inovalab_app.tarefas.models import EventoTarefa, Tarefa
from inovalab_app.tarefas.selectors import visible_tasks
from inovalab_app.tarefas.services import TaskConflict, delete_task, save_task, transition_task


class TaskServiceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_user('gestor')
        cls.admin.groups.add(Group.objects.get(name='Administradores'))
        cls.owner = get_user_model().objects.create_user('ana')
        cls.other = get_user_model().objects.create_user('bruno', is_staff=True)
        cls.service = make_service()
        cls.booking = make_booking(actor=cls.admin, service=cls.service)

    def create_task(self, **overrides):
        return save_task(actor=self.admin, data={
            'agendamento_servico': self.booking, 'responsavel': self.owner,
            'descricao': 'Produzir protótipo', **overrides,
        })

    def move(self, task, action, actor=None):
        return transition_task(actor=actor or self.admin, task_id=task.pk,
                               action=action, expected_version=task.versao)

    def test_create_trims_description_and_records_actor_and_initial_state(self):
        task = self.create_task(descricao='  Produzir protótipo  ')
        self.assertEqual(task.descricao, 'Produzir protótipo')
        self.assertEqual((task.status, task.versao), ('demanda', 1))
        self.assertIsNone(task.inicio)
        self.assertIsNone(task.prazo)
        self.assertIsNone(task.conclusao)
        event = task.eventos.get()
        self.assertEqual((event.acao, event.ator_id, event.status_novo), ('criar', self.admin.pk, 'demanda'))
        self.assertEqual(event.ator_nome, 'gestor')

    def test_scope_limits_regular_and_staff_users_to_own_tasks(self):
        mine = self.create_task()
        theirs = self.create_task(responsavel=self.other)
        self.assertEqual(set(visible_tasks(self.owner).values_list('pk', flat=True)), {mine.pk})
        self.assertEqual(set(visible_tasks(self.other).values_list('pk', flat=True)), {theirs.pk})
        self.assertEqual(visible_tasks(self.admin).count(), 2)
        self.assertFalse(visible_tasks(AnonymousUser()).exists())

    def test_only_business_admin_can_create_and_edit_metadata(self):
        task = self.create_task()
        for actor in (self.owner, self.other, AnonymousUser()):
            with self.subTest(actor=actor), self.assertRaises(PermissionDenied):
                save_task(actor=actor, data={'agendamento_servico': self.booking, 'responsavel': self.owner, 'descricao': 'Negada'})
        with self.assertRaises(PermissionDenied):
            save_task(actor=self.owner, task_id=task.pk, expected_version=1, data={'descricao': 'Negada'})
        self.assertEqual(Tarefa.objects.count(), 1)

    def test_superuser_can_manage_without_group_or_staff_policy_shortcut(self):
        actor = get_user_model().objects.create_superuser('tecnico')
        task = save_task(actor=actor, data={'agendamento_servico': self.booking, 'responsavel': self.owner, 'descricao': 'Técnica'})
        self.assertEqual(task.eventos.get().ator_id, actor.pk)

    def test_protected_fields_cannot_bypass_flow_and_invalid_update_is_atomic(self):
        task = self.create_task()
        for field, value in (('status', 'concluido'), ('inicio', timezone.now()),
                             ('conclusao', timezone.now()), ('versao', 9), ('excluida_em', timezone.now()), ('id', 9)):
            with self.subTest(field=field), self.assertRaises(ValidationError):
                save_task(actor=self.admin, task_id=task.pk, expected_version=1,
                          data={'descricao': 'Não salvar', field: value})
        with self.assertRaises(ValidationError):
            save_task(actor=self.admin, task_id=task.pk, expected_version=1, data={'descricao': '  '})
        task.refresh_from_db()
        self.assertEqual((task.descricao, task.versao, task.eventos.count()), ('Produzir protótipo', 1, 1))

    def test_new_assignments_require_active_user_and_available_service(self):
        self.other.is_active = False
        self.other.save()
        unavailable = make_booking(actor=self.admin, situacao='pendente')
        for data in ({'responsavel': self.other}, {'agendamento_servico': unavailable}):
            with self.subTest(data=data), self.assertRaises(ValidationError):
                self.create_task(**data)
        self.assertEqual(Tarefa.objects.count(), 0)
        self.assertEqual(EventoTarefa.objects.count(), 0)

    def test_existing_inactive_references_allow_metadata_edits_and_admin_transitions(self):
        task = self.create_task()
        self.owner.is_active = False
        self.owner.save()
        self.booking.cancelado_em = timezone.now()
        self.booking.save()
        task = save_task(actor=self.admin, task_id=task.pk, expected_version=1,
                         data={'descricao': 'Manter referência', 'agendamento_servico': self.booking, 'responsavel': self.owner})
        task = self.move(task, 'iniciar')
        self.assertEqual(task.status, 'criacao')
        with self.assertRaises(PermissionDenied):
            self.move(task, 'enviar', self.owner)

    def test_owner_starts_and_submits_but_cannot_review_or_reopen(self):
        task = self.create_task()
        before = timezone.now()
        task = self.move(task, 'iniciar', self.owner)
        self.assertEqual(task.status, 'criacao')
        self.assertLessEqual(before, task.inicio)
        self.assertLessEqual(task.inicio, timezone.now())
        task = self.move(task, 'enviar', self.owner)
        self.assertEqual(task.status, 'avaliacao')
        for action in ('aprovar', 'recusar', 'reabrir'):
            with self.subTest(action=action), self.assertRaises(PermissionDenied):
                self.move(task, action, self.owner)
        task = self.move(task, 'aprovar')
        with self.assertRaises(PermissionDenied):
            self.move(task, 'reabrir', self.owner)
        self.assertEqual(task.versao, 4)

    def test_rejection_and_reopening_preserve_start_and_completion_history(self):
        task = self.move(self.create_task(), 'iniciar')
        started = task.inicio
        task = self.move(task, 'enviar')
        task = self.move(task, 'recusar')
        self.assertEqual(task.status, 'criacao')
        task = self.move(task, 'enviar')
        task = self.move(task, 'aprovar')
        completed = task.conclusao
        self.assertIsNotNone(completed)
        task = self.move(task, 'reabrir')
        self.assertEqual((task.status, task.inicio, task.conclusao), ('criacao', started, None))
        approval = task.eventos.get(acao='aprovar')
        self.assertEqual(approval.alteracoes['conclusao']['novo'], completed.isoformat())
        self.assertEqual(task.eventos.count(), 7)

    def test_invalid_transitions_and_foreign_ids_leave_task_and_events_unchanged(self):
        task = self.create_task()
        for action in ('enviar', 'aprovar', 'recusar', 'reabrir', 'inexistente'):
            with self.subTest(action=action), self.assertRaises(ValidationError):
                self.move(task, action)
        with self.assertRaises(Http404):
            self.move(task, 'iniciar', self.other)
        task.refresh_from_db()
        self.assertEqual((task.status, task.versao, task.eventos.count()), ('demanda', 1, 1))

    def test_reassignment_revokes_previous_owner_access_and_records_change(self):
        task = self.create_task()
        task = save_task(actor=self.admin, task_id=task.pk, expected_version=1, data={'responsavel': self.other})
        self.assertFalse(visible_tasks(self.owner).exists())
        self.assertEqual(visible_tasks(self.other).get().pk, task.pk)
        with self.assertRaises(Http404):
            self.move(task, 'iniciar', self.owner)
        event = task.eventos.get(acao='editar')
        self.assertEqual(event.alteracoes['responsavel'], {'anterior': self.owner.pk, 'novo': self.other.pk})

    def test_stale_edit_transition_and_delete_cannot_overwrite_new_version(self):
        task = self.create_task()
        task = save_task(actor=self.admin, task_id=task.pk, expected_version=1, data={'descricao': 'Nova versão'})
        for operation in (
            lambda: save_task(actor=self.admin, task_id=task.pk, expected_version=1, data={'descricao': 'Antiga'}),
            lambda: transition_task(actor=self.owner, task_id=task.pk, action='iniciar', expected_version=1),
            lambda: delete_task(actor=self.admin, task_id=task.pk, expected_version=1),
        ):
            with self.assertRaises(TaskConflict):
                operation()
        task.refresh_from_db()
        self.assertEqual((task.descricao, task.status, task.versao, task.eventos.count()), ('Nova versão', 'demanda', 2, 2))
        self.assertIsNone(task.excluida_em)

    def test_version_must_be_integer_positive_and_required(self):
        task = self.create_task()
        for version in (None, 0, -1, True, 1.5, '1'):
            with self.subTest(version=version), self.assertRaises(ValidationError):
                transition_task(actor=self.owner, task_id=task.pk, action='iniciar', expected_version=version)
        self.assertEqual(task.eventos.count(), 1)

    def test_delete_is_admin_only_soft_and_removes_all_visible_queries(self):
        task = self.create_task()
        with self.assertRaises(PermissionDenied):
            delete_task(actor=self.owner, task_id=task.pk, expected_version=1)
        delete_task(actor=self.admin, task_id=task.pk, expected_version=1)
        task.refresh_from_db()
        self.assertIsNotNone(task.excluida_em)
        self.assertEqual((task.versao, task.eventos.count()), (2, 2))
        self.assertEqual(task.eventos.get(acao='excluir').status_novo, 'demanda')
        for actor in (self.admin, self.owner):
            self.assertFalse(visible_tasks(actor).exists())
            with self.assertRaises(Http404):
                self.move(task, 'iniciar', actor)

    def test_referenced_service_and_owner_are_protected_from_deletion(self):
        self.create_task()
        for entry in (self.service, self.owner):
            with self.subTest(entry=entry), self.assertRaises(ProtectedError):
                entry.delete()

    def test_overdue_deadline_is_allowed_and_does_not_block_starting(self):
        deadline = timezone.now() - timedelta(days=1)
        task = self.move(self.create_task(prazo=deadline), 'iniciar', self.owner)
        self.assertEqual(task.prazo, deadline)
        self.assertGreater(task.inicio, deadline)
