from django.core.exceptions import ValidationError as ModelValidationError
from rest_framework import serializers

from inovalab_app.catalogo.models import Equipamento, Servico
from inovalab_app.catalogo.services import save_entry


class CatalogSerializer(serializers.ModelSerializer):
    def validate(self, attrs):
        if 'codigo_inicial' in self.initial_data:
            raise serializers.ValidationError({'codigo_inicial': 'Este campo não pode ser alterado.'})
        return super().validate(attrs)

    def persist(self, data, instance=None):
        try:
            return save_entry(
                actor=self.context['request'].user, model=self.Meta.model,
                data=data, instance=instance,
            )
        except ModelValidationError as error:
            errors = error.message_dict if hasattr(error, 'message_dict') else {'non_field_errors': error.messages}
            if '__all__' in errors:
                errors['non_field_errors'] = errors.pop('__all__')
            raise serializers.ValidationError(errors) from error

    def create(self, validated_data):
        return self.persist(validated_data)

    def update(self, instance, validated_data):
        return self.persist(validated_data, instance)


class ServicoSerializer(CatalogSerializer):
    class Meta:
        model = Servico
        fields = ['id', 'titulo', 'descricao', 'prazo']
        read_only_fields = ['id']


class EquipamentoSerializer(CatalogSerializer):
    class Meta:
        model = Equipamento
        fields = ['id', 'nome', 'descricao', 'foto', 'status']
        read_only_fields = ['id']
