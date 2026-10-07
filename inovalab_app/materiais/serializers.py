from collections.abc import Mapping
from decimal import Decimal

from django.core.exceptions import ValidationError as ModelValidationError
from rest_framework import serializers

from inovalab_app.materiais.models import StatusMaterial
from inovalab_app.materiais.services import PUBLIC_FIELDS, save_material


class MaterialSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    nome = serializers.CharField(max_length=150)
    categoria = serializers.CharField(max_length=100)
    quantidade = serializers.DecimalField(max_digits=12, decimal_places=3, min_value=Decimal('0'),
                                          max_value=Decimal('999999999.999'), coerce_to_string=True)
    unidade = serializers.CharField(max_length=20)
    status = serializers.ChoiceField(choices=StatusMaterial.choices, required=False)
    fonte = serializers.CharField(max_length=150)
    versao = serializers.IntegerField(min_value=1, max_value=9223372036854775806, required=False)

    def to_internal_value(self, data):
        if not isinstance(data, Mapping):
            raise serializers.ValidationError({'non_field_errors': 'Informe um objeto JSON.'})
        unknown = set(data) - set(PUBLIC_FIELDS) - {'versao'}
        if unknown:
            raise serializers.ValidationError({field: 'Este campo não pode ser alterado.' for field in unknown})
        if 'versao' in data and type(data['versao']) is not int:
            raise serializers.ValidationError({'versao': 'Informe uma versão inteira.'})
        for field in ('nome', 'categoria', 'unidade', 'fonte'):
            if field in data and not isinstance(data[field], str):
                raise serializers.ValidationError({field: 'Informe um texto.'})
        return super().to_internal_value(data)

    def validate(self, attrs):
        if self.instance is None and 'versao' in attrs:
            raise serializers.ValidationError({'versao': 'A versão inicial é definida pelo sistema.'})
        if self.instance is not None:
            if 'versao' not in attrs:
                raise serializers.ValidationError({'versao': 'Informe a versão do material.'})
            if not self.partial and 'status' not in attrs:
                raise serializers.ValidationError({'status': 'Este campo é obrigatório.'})
        return attrs

    def _persist(self, data, instance=None):
        version = data.pop('versao', None)
        try:
            return save_material(actor=self.context['request'].user, data=data,
                                 material_id=instance.pk if instance else None, expected_version=version)
        except ModelValidationError as error:
            errors = error.message_dict if hasattr(error, 'message_dict') else {'non_field_errors': error.messages}
            if '__all__' in errors:
                errors['non_field_errors'] = errors.pop('__all__')
            raise serializers.ValidationError(errors) from error

    def create(self, validated_data):
        return self._persist(validated_data)

    def update(self, instance, validated_data):
        return self._persist(validated_data, instance)
