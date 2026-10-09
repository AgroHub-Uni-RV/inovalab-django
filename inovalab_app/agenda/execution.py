"""Read-only execution policy; approval and task workflow stay independent."""
from dataclasses import dataclass
from datetime import datetime

from django.core.exceptions import ValidationError
from django.db.models import Count, Max, Q
from django.utils import timezone


EXECUTION_LABELS = {
    'nao_aplicavel': 'Não aplicável',
    'aguardando_inicio': 'Aguardando início',
    'em_execucao': 'Em execução',
    'concluido': 'Concluído',
    'aguardando_encerramento': 'Aguardando encerramento',
}
EXECUTION_CHOICES = [('aguardando_inicio', 'Aguardando início'), ('em_execucao', 'Em execução'),
                     ('concluido', 'Concluídos'), ('atrasado', 'Atrasados'),
                     ('aguardando_encerramento', 'Aguardando encerramento')]


@dataclass(frozen=True)
class TaskExecutionFacts:
    total: int
    pendentes: int
    iniciadas: int
    ultima_conclusao: datetime | None


@dataclass(frozen=True)
class ExecutionState:
    estado: str
    rotulo: str
    atrasado: bool = False
    concluido_com_atraso: bool = False
    concluido_em: datetime | None = None


def classify_execution(*, category: str, situation: str, cancelled: bool, now: datetime,
                       deadline: datetime | None = None, tasks: TaskExecutionFacts | None = None,
                       start: datetime | None = None, end: datetime | None = None,
                       realized_at: datetime | None = None) -> ExecutionState:
    state, overdue, late, completed = 'nao_aplicavel', False, False, None
    if situation == 'confirmado' and not cancelled:
        if category == 'servico':
            facts = tasks or TaskExecutionFacts(0, 0, 0, None)
            if facts.total and not facts.pendentes:
                state, completed = 'concluido', facts.ultima_conclusao
                late = bool(completed and deadline and completed > deadline)
            else:
                state = 'em_execucao' if facts.iniciadas else 'aguardando_inicio'
                overdue = bool(deadline and now > deadline)
        elif category == 'visita':
            if realized_at is not None:
                state, completed = 'concluido', realized_at
            elif now < start:
                state = 'aguardando_inicio'
            elif now < end:
                state = 'em_execucao'
            else:
                state = 'aguardando_encerramento'
    return ExecutionState(state, EXECUTION_LABELS[state], overdue, late, completed)


def _task_aggregates(prefix=''):
    valid = Q(**{prefix + 'excluida_em__isnull': True})
    return {
        '_exec_total': Count(prefix + 'pk', filter=valid, distinct=True),
        '_exec_pendentes': Count(prefix + 'pk', filter=valid & ~Q(**{prefix + 'status': 'concluido'}), distinct=True),
        '_exec_iniciadas': Count(prefix + 'pk', filter=valid & Q(**{prefix + 'inicio__isnull': False}), distinct=True),
        '_exec_ultima_conclusao': Max(prefix + 'conclusao', filter=valid & Q(**{prefix + 'status': 'concluido'})),
    }


def annotate_service_execution(queryset):
    return queryset.annotate(**_task_aggregates('tarefas__'))


def execution_for(booking, *, now=None):
    now = now if now is not None else timezone.now()
    facts = None
    if booking.categoria == 'servico' and booking.situacao == 'confirmado' and not booking.cancelado_em:
        values = (vars(booking) if hasattr(booking, '_exec_total')
                  else booking.tarefas.aggregate(**_task_aggregates()))
        facts = TaskExecutionFacts(*(values[name] for name in (
            '_exec_total', '_exec_pendentes', '_exec_iniciadas', '_exec_ultima_conclusao')))
    return classify_execution(category=booking.categoria, situation=booking.situacao,
        cancelled=bool(booking.cancelado_em), now=now,
        deadline=booking.servico.prazo if booking.categoria == 'servico' else None, tasks=facts,
        start=booking.inicio if booking.categoria == 'visita' else None,
        end=booking.fim if booking.categoria == 'visita' else None,
        realized_at=getattr(booking, 'realizada_em', None))


def prepare_execution(rows, *, now):
    for row in rows:
        booking = getattr(row, 'booking', row)
        booking._execucao = execution_for(booking, now=now)
    return rows


def filter_execution(rows, value=''):
    if value not in {'', *(key for key, label in EXECUTION_CHOICES)}:
        raise ValidationError({'execucao': 'Selecione uma execução válida.'})
    if not value:
        return rows
    return [row for row in rows if (row.atrasado if value == 'atrasado' else row.estado_execucao == value)]
