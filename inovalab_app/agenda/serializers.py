from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal

from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import serializers

from inovalab_app.agenda.models import EventoAgendamento
from inovalab_app.agenda.services import CATEGORY_MODELS, save_booking
from inovalab_app.catalogo.models import Equipamento
from inovalab_app.materiais.models import Material
from inovalab_app.tarefas.serializers import TaskSerializer


class StrictPayloadMixin:
    def to_internal_value(self, data):
        if not isinstance(data, Mapping):
            raise serializers.ValidationError({'non_field_errors': ['Informe um objeto JSON.']})
        writable = {key for key, field in self.fields.items() if not field.read_only}
        unknown = set(data) - writable
        if unknown:
            raise serializers.ValidationError({key: 'Este campo não pode ser alterado.' for key in unknown})
        return super().to_internal_value(data)


class VersionField(serializers.IntegerField):
    def to_internal_value(self, data):
        if type(data) is not int:
            self.fail('invalid')
        return super().to_internal_value(data)


class AwareDateTimeField(serializers.DateTimeField):
    def to_internal_value(self, data):
        try:
            value = data if isinstance(data, datetime) else parse_datetime(data) if isinstance(data, str) else None
        except ValueError:
            value = None
        if value is None or timezone.is_naive(value):
            raise serializers.ValidationError('Informe data e hora ISO 8601 com fuso horário.')
        return super().to_internal_value(data)


class BookingSerializer(StrictPayloadMixin, serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    categoria = serializers.ChoiceField(choices=['servico'], default='servico')
    titulo = serializers.CharField(source='servico.titulo', max_length=150)
    descricao = serializers.CharField(source='servico.descricao')
    prazo = AwareDateTimeField(source='servico.prazo')
    observacoes = serializers.CharField(required=False, allow_blank=True)
    objeto_nome = serializers.CharField(read_only=True)
    versao = VersionField(min_value=1, required=False)
    criado_por = serializers.IntegerField(source='criado_por_id', read_only=True)
    criado_por_nome = serializers.CharField(source='criador_nome', read_only=True)
    criado_em = serializers.DateTimeField(read_only=True)
    situacao = serializers.CharField(read_only=True)
    cancelado_em = serializers.DateTimeField(read_only=True)
    avaliado_por = serializers.IntegerField(source='avaliado_por_id', read_only=True)
    avaliado_em = serializers.DateTimeField(read_only=True)

    def to_representation(self, instance):
        if instance.categoria == 'visita':
            return VisitSerializer(instance, context=self.context).data
        if instance.categoria == 'equipamento':
            return LegacyEquipmentBookingSerializer(instance, context=self.context).data
        return super().to_representation(instance)

    def validate(self, attrs):
        attrs.update(attrs.pop('servico', {}))
        if self.instance is None and 'versao' in attrs:
            raise serializers.ValidationError({'versao': 'A versão inicial é definida pelo sistema.'})
        if self.instance is not None and 'versao' not in attrs:
            raise serializers.ValidationError({'versao': 'Informe a versão do agendamento.'})
        return attrs

    def create(self, validated_data):
        return save_booking(actor=self.context['request'].user, data=validated_data)

    def update(self, instance, validated_data):
        version = validated_data.pop('versao')
        return save_booking(actor=self.context['request'].user, category=instance.categoria, booking_id=instance.pk,
            expected_version=version, data=validated_data)


class LegacyEquipmentBookingSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    categoria = serializers.CharField(read_only=True)
    objeto = serializers.IntegerField(source='objeto_id', read_only=True)
    objeto_nome = serializers.CharField(read_only=True)
    motivo = serializers.CharField(read_only=True)
    observacoes = serializers.CharField(read_only=True)
    inicio = serializers.DateTimeField(read_only=True)
    fim = serializers.DateTimeField(read_only=True)
    versao = serializers.IntegerField(read_only=True)
    situacao = serializers.CharField(read_only=True)
    cancelado_em = serializers.DateTimeField(read_only=True)
    criado_por = serializers.IntegerField(source='criado_por_id', read_only=True)
    criado_por_nome = serializers.CharField(source='criador_nome', read_only=True)
    criado_em = serializers.DateTimeField(read_only=True)


class VisitSerializer(StrictPayloadMixin, serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    categoria = serializers.ChoiceField(choices=['visita'], default='visita')
    quantidade_pessoas = VersionField(min_value=1, max_value=2147483647)
    data = serializers.DateField()
    hora_inicio = serializers.TimeField()
    hora_termino = serializers.TimeField()
    observacoes = serializers.CharField(required=False, allow_blank=True)
    versao = VersionField(min_value=1, required=False)
    criado_por = serializers.IntegerField(source='criado_por_id', read_only=True)
    criado_por_nome = serializers.CharField(source='criador_nome', read_only=True)
    criado_em = serializers.DateTimeField(read_only=True)
    situacao = serializers.CharField(read_only=True)
    avaliado_por = serializers.IntegerField(source='avaliado_por_id', read_only=True)
    avaliado_em = serializers.DateTimeField(read_only=True)

    def validate(self, attrs):
        if self.instance is None and 'versao' in attrs:
            raise serializers.ValidationError({'versao': 'A versão inicial é definida pelo sistema.'})
        if self.instance is not None and 'versao' not in attrs:
            raise serializers.ValidationError({'versao': 'Informe a versão do agendamento.'})
        return attrs

    def create(self, validated_data):
        return save_booking(actor=self.context['request'].user, data=validated_data)

    def update(self, instance, validated_data):
        version = validated_data.pop('versao')
        return save_booking(actor=self.context['request'].user, category='visita', booking_id=instance.pk,
                            expected_version=version, data=validated_data)


class CancelSerializer(StrictPayloadMixin, serializers.Serializer):
    versao = VersionField(min_value=1)


class ConfirmationTaskSerializer(TaskSerializer):
    class Meta(TaskSerializer.Meta):
        fields = [name for name in TaskSerializer.Meta.fields if name != 'agendamento_servico']


class ServiceConfirmationSerializer(StrictPayloadMixin, serializers.Serializer):
    versao = VersionField(min_value=1)
    tarefa = ConfirmationTaskSerializer()


class EventSerializer(serializers.ModelSerializer):
    class Meta:
        model = EventoAgendamento
        fields = ['id', 'ator', 'ator_nome', 'instante', 'acao', 'alteracoes']
        read_only_fields = fields
