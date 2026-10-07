from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models


class StatusMaterial(models.TextChoices):
    DISPONIVEL = 'disponivel', 'Disponível'
    INDISPONIVEL = 'indisponivel', 'Indisponível'


class Material(models.Model):
    nome = models.CharField('nome', max_length=150)
    categoria = models.CharField('categoria', max_length=100)
    quantidade = models.DecimalField('quantidade', max_digits=12, decimal_places=3,
                                     validators=[MinValueValidator(Decimal('0'))])
    unidade = models.CharField('unidade', max_length=20)
    status = models.CharField('status', max_length=15, choices=StatusMaterial.choices,
                              default=StatusMaterial.DISPONIVEL)
    fonte = models.CharField('fonte / origem', max_length=150)
    versao = models.PositiveBigIntegerField('versão', default=1, editable=False)

    def clean_fields(self, exclude=None):
        excluded = set(exclude or ())
        for field in ('nome', 'categoria', 'unidade', 'fonte'):
            if field not in excluded and isinstance(getattr(self, field), str):
                setattr(self, field, getattr(self, field).strip())
        if 'quantidade' not in excluded:
            if isinstance(self.quantidade, bool):
                raise ValidationError({'quantidade': 'Informe uma quantidade decimal.'})
            if self.quantidade is not None:
                try:
                    # Django rounds float inputs to max_digits before running DecimalValidator.
                    self.quantidade = Decimal(str(self.quantidade))
                except (InvalidOperation, ValueError):
                    raise ValidationError({'quantidade': 'Informe uma quantidade decimal.'})
        super().clean_fields(exclude=exclude)

    def __str__(self):
        return self.nome

    class Meta:
        db_table = 'materiais_material'
        ordering = ['nome', 'pk']
        verbose_name = 'material'
        verbose_name_plural = 'materiais'
        constraints = [
            models.CheckConstraint(condition=models.Q(quantidade__gte=0, quantidade__lte=Decimal('999999999.999')),
                                   name='material_quantidade_valida'),
            models.CheckConstraint(condition=models.Q(status__in=StatusMaterial.values), name='material_status_valido'),
            models.CheckConstraint(condition=models.Q(versao__gte=1), name='material_versao_positiva'),
        ]
