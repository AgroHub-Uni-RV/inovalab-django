from rest_framework import serializers

from agenda.models import CATEGORIES
from agenda.serializers import AwareDateTimeField, StrictPayloadMixin, VersionField
from integracoes.services import normalize_request


class ExternalIdField(serializers.CharField):
    def to_internal_value(self, data):
        if not isinstance(data, str):
            self.fail('invalid')
        return super().to_internal_value(data)


class ExternalBookingSerializer(StrictPayloadMixin, serializers.Serializer):
    id_externo = ExternalIdField(max_length=150)
    requerente_id = ExternalIdField(max_length=150)
    requerente = ExternalIdField(max_length=150)
    motivo = ExternalIdField(required=False)
    categoria = serializers.ChoiceField(choices={**CATEGORIES, 'espaco': 'Espaço (reenvio legado)'})
    objeto = VersionField(min_value=1, max_value=9223372036854775807, required=False)
    inicio = AwareDateTimeField()
    fim = AwareDateTimeField()

    def validate(self, attrs):
        return normalize_request(attrs)
