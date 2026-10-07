from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class StatusTarefa(models.TextChoices):
    DEMANDA = 'demanda', 'Demanda'
    CRIACAO = 'criacao', 'Criação'
    AVALIACAO = 'avaliacao', 'Avaliação'
    CONCLUIDO = 'concluido', 'Concluído'


class Tarefa(models.Model):
    servico = models.ForeignKey('inovalab_app.Servico', on_delete=models.PROTECT, verbose_name='serviço')
    descricao = models.TextField('descrição')
    responsavel = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, verbose_name='responsável')
    status = models.CharField('status', max_length=10, choices=StatusTarefa.choices, default=StatusTarefa.DEMANDA)
    inicio = models.DateTimeField('início', null=True, blank=True, editable=False)
    prazo = models.DateTimeField('prazo', null=True, blank=True)
    conclusao = models.DateTimeField('conclusão', null=True, blank=True, editable=False)
    versao = models.PositiveBigIntegerField(default=1, editable=False)
    excluida_em = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        db_table = 'tarefas_tarefa'
        ordering = ['-pk']
        verbose_name = 'tarefa'
        verbose_name_plural = 'tarefas'
        constraints = [
            models.CheckConstraint(condition=models.Q(status__in=StatusTarefa.values), name='tarefa_status_valido'),
            models.CheckConstraint(condition=models.Q(versao__gte=1), name='tarefa_versao_positiva'),
            models.CheckConstraint(
                condition=models.Q(status='demanda') | models.Q(inicio__isnull=False), name='tarefa_inicio_coerente',
            ),
            models.CheckConstraint(
                condition=(models.Q(status='concluido', conclusao__isnull=False)
                           | (~models.Q(status='concluido') & models.Q(conclusao__isnull=True))),
                name='tarefa_conclusao_coerente',
            ),
        ]

    def clean(self):
        super().clean()
        if isinstance(self.descricao, str):
            self.descricao = self.descricao.strip()
        if not self.descricao:
            raise ValidationError({'descricao': 'Informe uma descrição.'})

    def __str__(self):
        return f'Tarefa #{self.pk}'


class EventoTarefa(models.Model):
    tarefa = models.ForeignKey(Tarefa, on_delete=models.CASCADE, related_name='eventos')
    ator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    ator_nome = models.CharField(max_length=150)
    instante = models.DateTimeField(auto_now_add=True)
    acao = models.CharField(max_length=15)
    status_anterior = models.CharField(max_length=10, blank=True)
    status_novo = models.CharField(max_length=10)
    alteracoes = models.JSONField(default=dict)

    class Meta:
        db_table = 'tarefas_eventotarefa'
        ordering = ['-pk']
        verbose_name = 'evento de tarefa'
        verbose_name_plural = 'eventos de tarefas'
