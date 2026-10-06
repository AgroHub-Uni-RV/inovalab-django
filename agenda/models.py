from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


CATEGORIES = {'servico': 'Serviço', 'equipamento': 'Equipamento', 'espaco': 'Espaço'}


class Agendamento(models.Model):
    servico = models.ForeignKey('catalogo.Servico', on_delete=models.PROTECT, null=True, blank=True)
    equipamento = models.ForeignKey('catalogo.Equipamento', on_delete=models.PROTECT, null=True, blank=True)
    espaco = models.ForeignKey('catalogo.Espaco', on_delete=models.PROTECT, null=True, blank=True)
    equipamentos = models.ManyToManyField('catalogo.Equipamento', blank=True, related_name='agendamentos_de_servico')
    material_proprio = models.BooleanField('tem material próprio', null=True, blank=True)
    material_gasto_gramas = models.DecimalField(
        'material gasto (g)', max_digits=12, decimal_places=3, null=True, blank=True,
        validators=[MinValueValidator(Decimal('0.001'))],
    )
    requerente = models.CharField(max_length=150)
    motivo = models.TextField()
    inicio = models.DateTimeField()
    fim = models.DateTimeField()
    versao = models.PositiveBigIntegerField(default=1, editable=False)
    cancelado_em = models.DateTimeField(null=True, blank=True, editable=False)
    criado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, editable=False)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['inicio', 'pk']
        constraints = [
            models.CheckConstraint(condition=(
                models.Q(servico__isnull=False, equipamento__isnull=True, espaco__isnull=True)
                | models.Q(servico__isnull=True, equipamento__isnull=False, espaco__isnull=True)
                | models.Q(servico__isnull=True, equipamento__isnull=True, espaco__isnull=False)
            ), name='agenda_exatamente_um_alvo'),
            models.CheckConstraint(condition=models.Q(fim__gt=models.F('inicio')), name='agenda_intervalo_positivo'),
            models.CheckConstraint(condition=models.Q(versao__gte=1), name='agenda_versao_positiva'),
            models.CheckConstraint(condition=(
                models.Q(material_proprio__isnull=True, material_gasto_gramas__isnull=True)
                | models.Q(servico__isnull=False, material_proprio__isnull=False,
                           material_proprio=True, material_gasto_gramas__isnull=True)
                | models.Q(servico__isnull=False, material_proprio__isnull=False,
                           material_proprio=False, material_gasto_gramas__gt=0)
                  & models.Q(material_gasto_gramas__isnull=False)
            ), name='agenda_material_de_servico_valido'),
        ]
        indexes = [models.Index(fields=['inicio', 'fim'], name='agenda_periodo_idx')]

    @property
    def categoria(self):
        return next((name for name in CATEGORIES if getattr(self, name + '_id') is not None), None)

    @property
    def objeto_id(self):
        return getattr(self, self.categoria + '_id') if self.categoria else None

    @property
    def objeto_nome(self):
        return getattr(self, self.categoria).nome if self.categoria else ''

    @property
    def categoria_display(self):
        return {'servico': 'Serviços', 'equipamento': 'Equipamentos', 'espaco': 'Salas'}.get(self.categoria, '')

    def clean(self):
        errors = {}
        if self.categoria != 'servico' and (self.material_proprio is not None or self.material_gasto_gramas is not None):
            errors['material_proprio'] = 'Material é informado somente em agendamentos de serviço.'
        elif self.material_proprio is False and self.material_gasto_gramas is None:
            errors['material_gasto_gramas'] = 'Informe em gramas o material gasto do laboratório.'
        elif self.material_proprio is not False and self.material_gasto_gramas is not None:
            errors['material_gasto_gramas'] = 'O gasto é informado somente quando o material não é próprio.'
        for name in ('requerente', 'motivo'):
            value = getattr(self, name)
            if isinstance(value, str):
                setattr(self, name, value.strip())
            if not getattr(self, name):
                errors[name] = 'Este campo é obrigatório.'
        for name in ('inicio', 'fim'):
            value = getattr(self, name)
            if value is not None and timezone.is_naive(value):
                errors[name] = 'Informe data e hora com fuso horário.'
        if not errors and self.inicio and self.fim and self.fim <= self.inicio:
            errors['fim'] = 'O término deve ser posterior ao início.'
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f'{self.objeto_nome} — {self.requerente}'


class EventoAgendamento(models.Model):
    agendamento = models.ForeignKey(Agendamento, on_delete=models.CASCADE, related_name='eventos')
    ator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    ator_nome = models.CharField(max_length=150)
    instante = models.DateTimeField(auto_now_add=True)
    acao = models.CharField(max_length=15, choices=[('criar', 'Criar'), ('editar', 'Editar'), ('cancelar', 'Cancelar')])
    alteracoes = models.JSONField(default=dict)

    class Meta:
        ordering = ['-pk']
