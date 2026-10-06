from decimal import Decimal
from uuid import uuid4

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


CATEGORIES = {'servico': 'Serviço', 'equipamento': 'Equipamento', 'visita': 'Visita'}
BOOKING_STATUSES = {'pendente': 'Pendente', 'confirmado': 'Confirmado', 'rejeitado': 'Rejeitado'}


class Agendamento(models.Model):
    servico = models.ForeignKey('catalogo.Servico', on_delete=models.PROTECT, null=True, blank=True)
    equipamento = models.ForeignKey('catalogo.Equipamento', on_delete=models.PROTECT, null=True, blank=True)
    espaco = models.ForeignKey('catalogo.Espaco', on_delete=models.PROTECT, null=True, blank=True)
    visita = models.BooleanField(default=False)
    equipamentos = models.ManyToManyField('catalogo.Equipamento', blank=True, related_name='agendamentos_de_servico')
    material_proprio = models.BooleanField('tem material próprio', null=True, blank=True)
    material_gasto = models.ForeignKey('materiais.Material', on_delete=models.PROTECT, null=True, blank=True,
                                      verbose_name='material utilizado')
    material_gasto_gramas = models.DecimalField(
        'material gasto (g)', max_digits=12, decimal_places=3, null=True, blank=True,
        validators=[MinValueValidator(Decimal('0.001'))],
    )
    motivo = models.TextField(blank=True, default='')
    observacoes = models.TextField('observações', blank=True, default='')
    inicio = models.DateTimeField()
    fim = models.DateTimeField()
    versao = models.PositiveBigIntegerField(default=1, editable=False)
    cancelado_em = models.DateTimeField(null=True, blank=True, editable=False)
    criado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, editable=False)
    criado_em = models.DateTimeField(auto_now_add=True)
    situacao = models.CharField(max_length=10, choices=BOOKING_STATUSES.items(), default='confirmado', editable=False)
    avaliado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                     editable=False, related_name='agendamentos_avaliados')
    avaliado_em = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ['inicio', 'pk']
        constraints = [
            models.CheckConstraint(condition=(
                models.Q(visita=False) & (
                    models.Q(servico__isnull=False, equipamento__isnull=True, espaco__isnull=True)
                    | models.Q(servico__isnull=True, equipamento__isnull=False, espaco__isnull=True)
                    | models.Q(servico__isnull=True, equipamento__isnull=True, espaco__isnull=False)
                ) | models.Q(visita=True, servico__isnull=True, equipamento__isnull=True, espaco__isnull=True)
            ), name='agenda_exatamente_um_alvo'),
            models.CheckConstraint(condition=(models.Q(visita=False) | models.Q(motivo='', observacoes='')),
                                   name='agenda_visita_sem_textos'),
            models.CheckConstraint(condition=models.Q(fim__gt=models.F('inicio')), name='agenda_intervalo_positivo'),
            models.CheckConstraint(condition=models.Q(versao__gte=1), name='agenda_versao_positiva'),
            models.CheckConstraint(condition=models.Q(situacao__in=list(BOOKING_STATUSES)), name='agenda_situacao_valida'),
            models.CheckConstraint(condition=(
                models.Q(material_proprio__isnull=True, material_gasto_gramas__isnull=True)
                | models.Q(servico__isnull=False, material_proprio__isnull=False,
                           material_proprio=True, material_gasto_gramas__isnull=True)
                | models.Q(servico__isnull=False, material_proprio__isnull=False,
                           material_proprio=False, material_gasto_gramas__gt=0)
                  & models.Q(material_gasto_gramas__isnull=False)
            ), name='agenda_material_de_servico_valido'),
            models.CheckConstraint(condition=(
                models.Q(material_gasto__isnull=True)
                | models.Q(servico__isnull=False, material_proprio__isnull=False, material_proprio=False)
            ), name='agenda_tipo_material_valido'),
        ]
        indexes = [models.Index(fields=['inicio', 'fim'], name='agenda_periodo_idx')]

    @property
    def categoria(self):
        if self.visita:
            return 'visita'
        return next((name for name in ('servico', 'equipamento', 'espaco')
                     if getattr(self, name + '_id') is not None), None)

    @property
    def objeto_id(self):
        return getattr(self, self.categoria + '_id') if self.categoria and not self.visita else None

    @property
    def objeto_nome(self):
        return 'Visita' if self.visita else getattr(self, self.categoria).nome if self.categoria else ''

    @property
    def categoria_display(self):
        return {'servico': 'Serviços', 'equipamento': 'Equipamentos', 'visita': 'Visitas',
                'espaco': 'Espaço (legado)'}.get(self.categoria, '')

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

    def clean(self):
        errors = {}
        if isinstance(self.observacoes, str):
            self.observacoes = self.observacoes.strip()
        if self.material_gasto_id is not None and (self.categoria != 'servico' or self.material_proprio is not False):
            errors['material_gasto'] = 'Selecione material somente para serviços que utilizam material do laboratório.'
        if self.categoria != 'servico' and (self.material_proprio is not None or self.material_gasto_gramas is not None):
            errors['material_proprio'] = 'Material é informado somente em agendamentos de serviço.'
        elif self.material_proprio is False and self.material_gasto_gramas is None:
            errors['material_gasto_gramas'] = 'Informe em gramas o material gasto do laboratório.'
        elif self.material_proprio is not False and self.material_gasto_gramas is not None:
            errors['material_gasto_gramas'] = 'O gasto é informado somente quando o material não é próprio.'
        for name in ('motivo',):
            value = getattr(self, name)
            if isinstance(value, str):
                setattr(self, name, value.strip())
            if not self.visita and not getattr(self, name):
                errors[name] = 'Este campo é obrigatório.'
        if self.visita:
            for name in ('motivo', 'observacoes'):
                if getattr(self, name):
                    errors[name] = 'Visitas possuem somente dia e horários.'
        for name in ('inicio', 'fim'):
            value = getattr(self, name)
            if value is not None and timezone.is_naive(value):
                errors[name] = 'Informe data e hora com fuso horário.'
        if not errors and self.inicio and self.fim and self.fim <= self.inicio:
            errors['fim'] = 'O término deve ser posterior ao início.'
        if not errors and self.visita and self.inicio and self.fim:
            zone = timezone.get_default_timezone()
            if timezone.localtime(self.inicio, zone).date() != timezone.localtime(self.fim, zone).date():
                errors['fim'] = 'A visita deve começar e terminar no mesmo dia.'
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f'{self.objeto_nome} — {self.criador_nome}'


class ControleAgendaVisitas(models.Model):
    """Linha única usada para serializar alterações na agenda de visitas."""
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)


class ReservaAgroHub(models.Model):
    agendamento = models.OneToOneField(Agendamento, on_delete=models.CASCADE, related_name='reserva_agrohub')
    referencia = models.UUIDField(default=uuid4, unique=True, editable=False)
    origem = models.URLField(max_length=2048, editable=False)
    reserva_id = models.PositiveBigIntegerField(null=True, blank=True, editable=False)
    status_remoto = models.CharField(max_length=20, blank=True, editable=False)
    operacao = models.CharField(max_length=10, default='criar', editable=False)
    estado = models.CharField(max_length=12, default='pendente', editable=False,
        choices=[('pendente', 'Envio pendente'), ('enviando', 'Envio em andamento'),
                 ('registrada', 'Enviada ao AgroHub'), ('falha', 'Envio não concluído'), ('incerta', 'Aguardando conciliação')])
    payload = models.JSONField(default=dict, editable=False)
    mensagem = models.CharField(max_length=500, blank=True, editable=False)
    ultima_tentativa = models.DateTimeField(null=True, blank=True, editable=False)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['origem', 'reserva_id'], name='agrohub_reserva_origem_id_unico')]

    @property
    def status_display(self):
        return {'pendente': 'Pendente', 'confirmada': 'Confirmada', 'cancelada': 'Cancelada',
                'recusada': 'Recusada'}.get(self.status_remoto, 'Ainda não registrada')


class EventoAgendamento(models.Model):
    agendamento = models.ForeignKey(Agendamento, on_delete=models.CASCADE, related_name='eventos')
    ator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    ator_nome = models.CharField(max_length=150)
    instante = models.DateTimeField(auto_now_add=True)
    acao = models.CharField(max_length=15, choices=[('criar', 'Criar'), ('editar', 'Editar'), ('cancelar', 'Cancelar'),
                                                  ('aprovar', 'Aprovar'), ('rejeitar', 'Rejeitar')])
    alteracoes = models.JSONField(default=dict)

    class Meta:
        ordering = ['-pk']
