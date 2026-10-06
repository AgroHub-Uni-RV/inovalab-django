from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal

from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import serializers

from agenda.models import CATEGORIES, EventoAgendamento
from agenda.services import save_booking
from catalogo.models import Equipamento


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
    categoria = serializers.ChoiceField(choices=CATEGORIES)
    objeto = VersionField(source='objeto_id', min_value=1)
    objeto_nome = serializers.CharField(read_only=True)
    requerente = serializers.CharField(max_length=150)
    motivo = serializers.CharField()
    inicio = AwareDateTimeField()
    fim = AwareDateTimeField()
    equipamentos = serializers.PrimaryKeyRelatedField(queryset=Equipamento.objects.all(), many=True, required=False,
                                                      pk_field=VersionField(min_value=1))
    material_proprio = serializers.BooleanField(allow_null=True, required=False)
    material_gasto_gramas = serializers.DecimalField(max_digits=12, decimal_places=3, min_value=Decimal('0.001'),
                                                    allow_null=True, required=False)
    versao = VersionField(min_value=1, required=False)
    criado_por = serializers.IntegerField(source='criado_por_id', read_only=True)
    criado_em = serializers.DateTimeField(read_only=True)

    def validate(self, attrs):
        if 'equipamentos' in attrs:
            attrs['equipamentos'] = [equipment.pk for equipment in attrs['equipamentos']]
        if self.instance is None and 'versao' in attrs:
            raise serializers.ValidationError({'versao': 'A versão inicial é definida pelo sistema.'})
        if self.instance is not None and 'versao' not in attrs:
            raise serializers.ValidationError({'versao': 'Informe a versão do agendamento.'})
        if ('categoria' in attrs) != ('objeto_id' in attrs):
            raise serializers.ValidationError({'objeto': 'Informe categoria e objeto juntos.'})
        if 'objeto_id' in attrs:
            attrs['objeto'] = attrs.pop('objeto_id')
        return attrs

    def create(self, validated_data):
        return save_booking(actor=self.context['request'].user, data=validated_data)

    def update(self, instance, validated_data):
        version = validated_data.pop('versao')
        return save_booking(actor=self.context['request'].user, booking_id=instance.pk,
                            expected_version=version, data=validated_data)


class CancelSerializer(StrictPayloadMixin, serializers.Serializer):
    versao = VersionField(min_value=1)


class EventSerializer(serializers.ModelSerializer):
    class Meta:
        model = EventoAgendamento
        fields = ['id', 'ator', 'ator_nome', 'instante', 'acao', 'alteracoes']
        read_only_fields = fields
