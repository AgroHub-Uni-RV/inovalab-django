from django.core.exceptions import ValidationError
from django.db import models
from inovalab_app.catalogo.equipment_photos import EquipmentPhotoStorage


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
        db_table = 'catalogo_servico'
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
        db_table = 'catalogo_equipamento'
        ordering = ['nome', 'pk']
        verbose_name = 'equipamento'
        verbose_name_plural = 'equipamentos'
        constraints = [models.CheckConstraint(condition=models.Q(status__in=StatusRecurso.values), name='equipamento_status_valido')]
