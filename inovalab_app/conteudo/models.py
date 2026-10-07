from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class StatusBanner(models.TextChoices):
    ATIVO = 'ativo', 'Ativo'
    INATIVO = 'inativo', 'Inativo'
    AGENDADO = 'agendado', 'Agendado'


class LocalBanner(models.TextChoices):
    HOME = 'home', 'Início'
    SOBRE = 'sobre', 'Sobre'


class Banner(models.Model):
    titulo = models.CharField('título', max_length=150)
    texto_alternativo = models.CharField('texto alternativo', max_length=250, blank=True)
    banner_img = models.ImageField('imagem WebP', upload_to='banners/')
    status = models.CharField('status', max_length=8, choices=StatusBanner.choices, default=StatusBanner.INATIVO)
    local = models.CharField('local', max_length=5, choices=LocalBanner.choices, default=LocalBanner.HOME)
    ordem = models.PositiveIntegerField('ordem', default=0)
    inicio_exibicao = models.DateTimeField('início da exibição', null=True, blank=True)
    fim_exibicao = models.DateTimeField('fim da exibição', null=True, blank=True)
    versao = models.PositiveBigIntegerField('versão', default=1, editable=False)
    excluido_em = models.DateTimeField(null=True, blank=True, editable=False)

    def clean_fields(self, exclude=None):
        for name in ('titulo', 'texto_alternativo'):
            if name not in (exclude or ()) and isinstance(getattr(self, name), str):
                setattr(self, name, getattr(self, name).strip())
        super().clean_fields(exclude=exclude)

    def clean(self):
        super().clean()
        start, end = self.inicio_exibicao, self.fim_exibicao
        if self.status == StatusBanner.AGENDADO:
            if not start or not end:
                raise ValidationError({'inicio_exibicao': 'Informe início e fim para o banner agendado.'})
            if timezone.is_naive(start) or timezone.is_naive(end) or end <= start:
                raise ValidationError({'fim_exibicao': 'Informe um período com fuso e fim posterior ao início.'})
        elif start is not None or end is not None:
            raise ValidationError({'inicio_exibicao': 'Limpe o período para um banner ativo ou inativo.'})

    def __str__(self):
        return self.titulo

    class Meta:
        db_table = 'conteudo_banner'
        ordering = ['ordem', 'pk']
        verbose_name = 'banner'
        verbose_name_plural = 'banners'
        constraints = [
            models.CheckConstraint(condition=models.Q(status__in=StatusBanner.values), name='banner_status_valido'),
            models.CheckConstraint(condition=models.Q(local__in=LocalBanner.values), name='banner_local_valido'),
            models.CheckConstraint(condition=models.Q(ordem__gte=0, ordem__lte=2147483647), name='banner_ordem_valida'),
            models.CheckConstraint(condition=models.Q(versao__gte=1), name='banner_versao_positiva'),
            models.CheckConstraint(condition=(
                models.Q(status='agendado', inicio_exibicao__isnull=False, fim_exibicao__isnull=False,
                         fim_exibicao__gt=models.F('inicio_exibicao')) |
                models.Q(status__in=['ativo', 'inativo'], inicio_exibicao__isnull=True, fim_exibicao__isnull=True)
            ), name='banner_periodo_valido'),
        ]
