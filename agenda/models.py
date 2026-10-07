from datetime import datetime
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone

CATEGORIES = {'servico': 'Serviço', 'equipamento': 'Equipamento', 'visita': 'Visita'}
BOOKING_STATUSES = {'pendente': 'Pendente', 'confirmado': 'Confirmado', 'rejeitado': 'Rejeitado'}


class AgendaControle(models.Model):
    observacoes = models.TextField('observações', blank=True, default='')
    versao = models.PositiveBigIntegerField(default=1, editable=False)
    cancelado_em = models.DateTimeField(null=True, blank=True, editable=False)
    criado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, editable=False, related_name='%(class)s_criados')
    criado_em = models.DateTimeField(auto_now_add=True)
    situacao = models.CharField(max_length=10, choices=BOOKING_STATUSES.items(), default='confirmado', editable=False)
    avaliado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                     editable=False, related_name='%(class)s_avaliados')
    avaliado_em = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        abstract = True

    def get_absolute_url(self):
        return reverse('agenda:detail', kwargs={'category': self.categoria, 'pk': self.pk})

    @property
    def criador_nome(self):
        if self.criado_por:
            return self.criado_por.get_full_name() or self.criado_por.username
        if self.pk is None:
            return 'Não registrado'
        events = getattr(self, 'eventos_de_criacao', None)
        if events is not None:
            return events[0].ator_nome if events else 'Não registrado'
        return self.eventos.filter(acao='criar').values_list('ator_nome', flat=True).first() or 'Não registrado'

    def __str__(self):
        return f'{self.objeto_nome} — {self.criador_nome}'


class AgendaBase(AgendaControle):
    motivo = models.TextField(blank=True, default='')
    inicio = models.DateTimeField()
    fim = models.DateTimeField()
    class Meta:
        abstract = True
        ordering = ['inicio', 'pk']
        constraints = [
            models.CheckConstraint(condition=models.Q(fim__gt=models.F('inicio')), name='%(class)s_intervalo_positivo'),
            models.CheckConstraint(condition=models.Q(versao__gte=1), name='%(class)s_versao_positiva'),
            models.CheckConstraint(condition=models.Q(situacao__in=list(BOOKING_STATUSES)), name='%(class)s_situacao_valida'),
        ]
        indexes = [models.Index(fields=['inicio', 'fim'], name='%(class)s_periodo_idx')]

    @property
    def objeto_id(self):
        return getattr(self, self.categoria + '_id')

    @property
    def objeto_nome(self):
        return getattr(self, self.categoria).nome

    @property
    def categoria_display(self):
        return {'servico': 'Serviços', 'equipamento': 'Equipamentos'}[self.categoria]

    def clean(self):
        errors = {}
        self.motivo = self.motivo.strip() if isinstance(self.motivo, str) else self.motivo
        self.observacoes = self.observacoes.strip() if isinstance(self.observacoes, str) else self.observacoes
        if not self.motivo:
            errors['motivo'] = 'Este campo é obrigatório.'
        for name in ('inicio', 'fim'):
            value = getattr(self, name)
            if value is not None and timezone.is_naive(value):
                errors[name] = 'Informe data e hora com fuso horário.'
        if not errors and self.inicio and self.fim and self.fim <= self.inicio:
            errors['fim'] = 'O término deve ser posterior ao início.'
        if errors:
            raise ValidationError(errors)


class AgendaServico(AgendaBase):
    categoria = 'servico'
    servico = models.ForeignKey('catalogo.Servico', on_delete=models.PROTECT)
    equipamentos = models.ManyToManyField('catalogo.Equipamento', blank=True, related_name='agendamentos_de_servico')
    material_proprio = models.BooleanField('tem material próprio', null=True, blank=True)
    material_gasto = models.ForeignKey('materiais.Material', on_delete=models.PROTECT, null=True, blank=True,
                                      verbose_name='material utilizado')
    material_gasto_gramas = models.DecimalField(
        'material gasto (g)', max_digits=12, decimal_places=3, null=True, blank=True,
        validators=[MinValueValidator(Decimal('0.001'))],
    )

    class Meta(AgendaBase.Meta):
        abstract = False
        constraints = AgendaBase.Meta.constraints + [
            models.CheckConstraint(condition=(
                models.Q(material_proprio__isnull=True, material_gasto_gramas__isnull=True)
                | models.Q(material_proprio=True, material_proprio__isnull=False, material_gasto_gramas__isnull=True)
                | models.Q(material_proprio=False, material_proprio__isnull=False, material_gasto_gramas__gt=0, material_gasto_gramas__isnull=False)
            ), name='agendaservico_material_valido'),
            models.CheckConstraint(condition=(models.Q(material_gasto__isnull=True)
                | models.Q(material_proprio=False, material_proprio__isnull=False)), name='agendaservico_tipo_material_valido'),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.material_gasto_id is not None and self.material_proprio is not False:
            errors['material_gasto'] = 'Selecione material somente para serviços que utilizam material do laboratório.'
        if self.material_proprio is False and self.material_gasto_gramas is None:
            errors['material_gasto_gramas'] = 'Informe em gramas o material gasto do laboratório.'
        elif self.material_proprio is not False and self.material_gasto_gramas is not None:
            errors['material_gasto_gramas'] = 'O gasto é informado somente quando o material não é próprio.'
        if errors:
            raise ValidationError(errors)


class AgendaEquipamento(AgendaBase):
    categoria = 'equipamento'
    equipamento = models.ForeignKey('catalogo.Equipamento', on_delete=models.PROTECT)


class AgendaVisita(AgendaControle):
    categoria = 'visita'
    visita = True
    objeto_id = 0
    objeto_nome = 'Visita ao InovaLab'
    categoria_display = 'Visitas'
    motivo = ''
    quantidade_pessoas = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    data = models.DateField()
    hora_inicio = models.TimeField()
    hora_termino = models.TimeField()

    @property
    def inicio(self):
        return timezone.make_aware(datetime.combine(self.data, self.hora_inicio))

    @property
    def fim(self):
        return timezone.make_aware(datetime.combine(self.data, self.hora_termino))

    def clean(self):
        errors = {}
        if self.hora_inicio and self.hora_termino and self.hora_termino <= self.hora_inicio:
            errors['hora_termino'] = 'O término deve ser posterior ao início, no mesmo dia.'
        self.observacoes = self.observacoes.strip() if isinstance(self.observacoes, str) else self.observacoes
        if errors:
            raise ValidationError(errors)

    class Meta:
        ordering = ['data', 'hora_inicio', 'pk']
        constraints = [
            models.CheckConstraint(condition=models.Q(quantidade_pessoas__gte=1), name='agendavisita_pessoas_positivas'),
            models.CheckConstraint(condition=models.Q(hora_termino__gt=models.F('hora_inicio')), name='agendavisita_periodo_positivo'),
            models.CheckConstraint(condition=models.Q(versao__gte=1), name='agendavisita_versao_positiva'),
            models.CheckConstraint(condition=models.Q(situacao__in=list(BOOKING_STATUSES)), name='agendavisita_situacao_valida'),
        ]
        indexes = [models.Index(fields=['data', 'hora_inicio', 'hora_termino'], name='agendavisita_periodo_idx')]


BOOKING_MODELS = {'servico': AgendaServico, 'equipamento': AgendaEquipamento, 'visita': AgendaVisita}


class EventoAgendamento(models.Model):
    agenda_servico = models.ForeignKey(AgendaServico, on_delete=models.CASCADE, related_name='eventos', null=True, blank=True)
    agenda_equipamento = models.ForeignKey(AgendaEquipamento, on_delete=models.CASCADE, related_name='eventos', null=True, blank=True)
    agenda_visita = models.ForeignKey(AgendaVisita, on_delete=models.CASCADE, related_name='eventos', null=True, blank=True)
    ator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    ator_nome = models.CharField(max_length=150)
    instante = models.DateTimeField(auto_now_add=True)
    acao = models.CharField(max_length=15, choices=[('criar', 'Criar'), ('editar', 'Editar'), ('cancelar', 'Cancelar'),
                                                  ('aprovar', 'Aprovar'), ('rejeitar', 'Rejeitar')])
    alteracoes = models.JSONField(default=dict)

    @property
    def agendamento(self):
        return self.agenda_servico or self.agenda_equipamento or self.agenda_visita

    class Meta:
        ordering = ['-pk']
        constraints = [models.CheckConstraint(condition=(
            models.Q(agenda_servico__isnull=False, agenda_equipamento__isnull=True, agenda_visita__isnull=True)
            | models.Q(agenda_servico__isnull=True, agenda_equipamento__isnull=False, agenda_visita__isnull=True)
            | models.Q(agenda_servico__isnull=True, agenda_equipamento__isnull=True, agenda_visita__isnull=False)
        ), name='evento_exatamente_uma_agenda')]
