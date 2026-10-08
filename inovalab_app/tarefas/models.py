from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class StatusTarefa(models.TextChoices):
    DEMANDA = 'demanda', 'Demanda'
    CRIACAO = 'criacao', 'Criação'
    AVALIACAO = 'avaliacao', 'Avaliação'
    CONCLUIDO = 'concluido', 'Concluído'


class Tarefa(models.Model):
    agendamento_servico = models.ForeignKey('inovalab_app.AgendaServico', on_delete=models.PROTECT, related_name='tarefas', verbose_name='agendamento de serviço')
    servico_legado = models.ForeignKey('inovalab_app.ServicoLegado', on_delete=models.PROTECT, null=True, blank=True, editable=False)
    equipamento = models.ForeignKey('inovalab_app.Equipamento', on_delete=models.PROTECT, null=True, blank=True, verbose_name='equipamento')
    material_gasto = models.ForeignKey('inovalab_app.Material', on_delete=models.PROTECT, null=True, blank=True, verbose_name='material gasto')
    quantidade_material_gasto = models.CharField('quantidade de material gasto', max_length=150, blank=True, default='')
    responsaveis = models.ManyToManyField(settings.AUTH_USER_MODEL, through='TarefaResponsavel',
                                         related_name='tarefas_atribuidas', verbose_name='responsáveis')
    equipamentos = models.ManyToManyField('inovalab_app.Equipamento', through='TarefaEquipamento',
                                         related_name='tarefas_associadas', blank=True, verbose_name='equipamentos')
    descricao = models.TextField('descrição')
    responsavel = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, verbose_name='responsável')
    status = models.CharField('status', max_length=10, choices=StatusTarefa.choices, default=StatusTarefa.DEMANDA)
    inicio = models.DateTimeField('início', null=True, blank=True, editable=False)
    prazo_legado = models.DateTimeField('prazo anterior', db_column='prazo', null=True, blank=True, editable=False)
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

    @property
    def servico(self):
        return self.agendamento_servico.servico

    @property
    def servico_id(self):
        return self.agendamento_servico.servico_id

    @property
    def prazo(self):
        return self.servico.prazo

    @property
    def responsaveis_nomes(self):
        return ', '.join(user.get_full_name() or user.username for user in self.responsaveis.all())


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


class TarefaResponsavel(models.Model):
    tarefa = models.ForeignKey(Tarefa, on_delete=models.CASCADE, related_name='vinculos_responsaveis')
    responsavel = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)

    class Meta:
        db_table = 'tarefas_responsavel'
        constraints = [models.UniqueConstraint(fields=['tarefa', 'responsavel'], name='tarefa_responsavel_unico')]


class TarefaEquipamento(models.Model):
    tarefa = models.ForeignKey(Tarefa, on_delete=models.CASCADE, related_name='vinculos_equipamentos')
    equipamento = models.ForeignKey('inovalab_app.Equipamento', on_delete=models.PROTECT)

    class Meta:
        db_table = 'tarefas_equipamento'
        constraints = [models.UniqueConstraint(fields=['tarefa', 'equipamento'], name='tarefa_equipamento_unico')]


class TarefaMaterial(models.Model):
    tarefa = models.ForeignKey(Tarefa, on_delete=models.CASCADE, related_name='materiais_gastos')
    material = models.ForeignKey('inovalab_app.Material', on_delete=models.PROTECT)
    quantidade = models.CharField('quantidade gasta', max_length=150, blank=True, default='')

    class Meta:
        db_table = 'tarefas_material'
        ordering = ['material_id']
        constraints = [models.UniqueConstraint(fields=['tarefa', 'material'], name='tarefa_material_unico')]
