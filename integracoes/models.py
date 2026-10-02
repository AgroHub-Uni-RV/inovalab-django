import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class ClienteIntegracao(models.Model):
    nome = models.CharField(max_length=100, unique=True)
    identificador = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    ativo = models.BooleanField(default=True)
    token_digest = models.CharField(max_length=64, blank=True, editable=False)
    versao = models.PositiveBigIntegerField(default=1, editable=False)
    criado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, editable=False)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['nome', 'pk']
        constraints = [models.CheckConstraint(condition=models.Q(versao__gte=1), name='integracoes_versao_positiva')]

    def clean(self):
        self.nome = self.nome.strip()
        if not self.nome:
            raise ValidationError({'nome': 'Informe o nome do sistema.'})

    def __str__(self):
        return self.nome


class PedidoIntegracao(models.Model):
    cliente = models.ForeignKey(ClienteIntegracao, on_delete=models.PROTECT, related_name='pedidos')
    id_externo = models.CharField(max_length=150)
    requerente_id = models.CharField(max_length=150)
    conteudo_digest = models.CharField(max_length=64, editable=False)
    agendamento = models.OneToOneField('agenda.Agendamento', on_delete=models.PROTECT, related_name='pedido_integracao')
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-pk']
        constraints = [models.UniqueConstraint(fields=['cliente', 'id_externo'], name='integracoes_pedido_unico')]
