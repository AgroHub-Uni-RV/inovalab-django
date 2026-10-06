from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from catalogo.equipment_photos import EquipmentPhotoStorage


class StatusServico(models.TextChoices):
    DISPONIVEL = 'disponivel', 'Disponível'
    INDISPONIVEL = 'indisponivel', 'Indisponível'


class StatusRecurso(models.TextChoices):
    DISPONIVEL = 'disponivel', 'Disponível'
    OCUPADO = 'ocupado', 'Ocupado'
    INDISPONIVEL = 'indisponivel', 'Indisponível'


class CadastroBase(models.Model):
    nome = models.CharField('nome', max_length=150)

    class Meta:
        abstract = True

    def clean(self):
        super().clean()
        if isinstance(self.nome, str):
            self.nome = self.nome.strip()
        if not self.nome:
            raise ValidationError({'nome': 'Informe um nome.'})

    def __str__(self):
        return self.nome


class Servico(CadastroBase):
    descricao = models.TextField('descrição', blank=True)
    status = models.CharField('status', max_length=15, choices=StatusServico.choices, default=StatusServico.DISPONIVEL)
    codigo_inicial = models.CharField(max_length=40, null=True, blank=True, unique=True, editable=False)

    class Meta:
        ordering = ['nome', 'pk']
        verbose_name = 'serviço'
        verbose_name_plural = 'serviços'
        constraints = [models.CheckConstraint(condition=models.Q(status__in=StatusServico.values), name='servico_status_valido')]


class Equipamento(CadastroBase):
    codigo_inicial = models.CharField(max_length=40, null=True, blank=True, unique=True, editable=False)
    descricao = models.TextField('descrição', blank=True)
    foto = models.ImageField('foto', upload_to='equipamentos/', storage=EquipmentPhotoStorage(), blank=True)
    status = models.CharField('status', max_length=15, choices=StatusRecurso.choices, default=StatusRecurso.DISPONIVEL)

    class Meta:
        ordering = ['nome', 'pk']
        verbose_name = 'equipamento'
        verbose_name_plural = 'equipamentos'
        constraints = [models.CheckConstraint(condition=models.Q(status__in=StatusRecurso.values), name='equipamento_status_valido')]


class Espaco(CadastroBase):
    codigo_inicial = models.CharField(max_length=40, null=True, blank=True, unique=True, editable=False)
    somente_administradores = models.BooleanField('agendamento exclusivo de administradores', default=False)
    capacidade_maxima_de_pessoas = models.PositiveIntegerField(
        'capacidade máxima de pessoas', null=True, blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(2147483647)],
    )
    status = models.CharField('status', max_length=15, choices=StatusRecurso.choices, default=StatusRecurso.DISPONIVEL)

    def clean_fields(self, exclude=None):
        field = 'capacidade_maxima_de_pessoas'
        value = self.capacidade_maxima_de_pessoas
        if field not in (exclude or ()) and value is not None:
            # IntegerField converts values before running validators; validate the original first.
            try:
                number = Decimal(str(value))
            except (InvalidOperation, ValueError, TypeError):
                raise ValidationError({field: 'Informe uma capacidade inteira.'})
            if not number.is_finite() or number != number.to_integral_value():
                raise ValidationError({field: 'Informe uma capacidade inteira.'})
        super().clean_fields(exclude=exclude)

    class Meta:
        ordering = ['nome', 'pk']
        verbose_name = 'espaço'
        verbose_name_plural = 'espaços'
        constraints = [
            models.CheckConstraint(
                condition=models.Q(capacidade_maxima_de_pessoas__gte=1, capacidade_maxima_de_pessoas__lte=2147483647),
                name='espaco_capacidade_valida',
            ),
            models.CheckConstraint(condition=models.Q(status__in=StatusRecurso.values), name='espaco_status_valido'),
        ]
