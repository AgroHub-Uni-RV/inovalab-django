from collections.abc import Mapping

from rest_framework import serializers

from tarefas.models import EventoTarefa, Tarefa
from tarefas.services import TRANSITIONS, allowed_actions, save_task


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


class TaskSerializer(StrictPayloadMixin, serializers.ModelSerializer):
    versao = VersionField(min_value=1, required=False)
    servico_nome = serializers.CharField(source='servico.nome', read_only=True)
    responsavel_nome = serializers.CharField(source='responsavel.username', read_only=True)
    acoes_permitidas = serializers.SerializerMethodField()

    class Meta:
        model = Tarefa
        fields = ['id', 'servico', 'servico_nome', 'descricao', 'responsavel', 'responsavel_nome',
                  'status', 'inicio', 'prazo', 'conclusao', 'versao', 'acoes_permitidas']
        read_only_fields = ['id', 'status', 'inicio', 'conclusao']

    def get_acoes_permitidas(self, task):
        return allowed_actions(self.context['request'].user, task)

    def validate(self, attrs):
        if self.instance is None and 'versao' in attrs:
            raise serializers.ValidationError({'versao': 'A versão inicial é definida pelo sistema.'})
        if self.instance is not None and 'versao' not in attrs:
            raise serializers.ValidationError({'versao': 'Informe a versão da tarefa.'})
        return attrs

    def create(self, validated_data):
        return save_task(actor=self.context['request'].user, data=validated_data)

    def update(self, instance, validated_data):
        version = validated_data.pop('versao')
        return save_task(actor=self.context['request'].user, task_id=instance.pk,
                         expected_version=version, data=validated_data)


class TransitionSerializer(StrictPayloadMixin, serializers.Serializer):
    acao = serializers.ChoiceField(choices=list(TRANSITIONS))
    versao = VersionField(min_value=1)


class DeleteSerializer(StrictPayloadMixin, serializers.Serializer):
    versao = VersionField(min_value=1)


class EventSerializer(serializers.ModelSerializer):
    class Meta:
        model = EventoTarefa
        fields = ['id', 'ator', 'ator_nome', 'instante', 'acao', 'status_anterior', 'status_novo', 'alteracoes']
        read_only_fields = fields
