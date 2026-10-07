from collections.abc import Mapping
from datetime import datetime

from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import serializers

from inovalab_app.conteudo.models import LocalBanner, StatusBanner
from inovalab_app.conteudo.services import save_banner


class StrictPayloadMixin:
    def to_internal_value(self, data):
        if not isinstance(data, Mapping):
            raise serializers.ValidationError({'non_field_errors': ['Informe um objeto de campos.']})
        unknown = set(data) - {key for key, field in self.fields.items() if not field.read_only}
        if unknown:
            raise serializers.ValidationError({key: 'Este campo não pode ser alterado.' for key in unknown})
        if hasattr(data, 'lists') and any(len(values) != 1 for _, values in data.lists()):
            raise serializers.ValidationError('Envie cada campo uma única vez.')
        return super().to_internal_value(data)


class StrictIntegerField(serializers.IntegerField):
    def to_internal_value(self, data):
        request = self.context.get('request')
        multipart = request is not None and request.content_type.startswith('multipart/form-data')
        if multipart and isinstance(data, str) and data.isascii() and data.isdecimal():
            data = int(data)
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


def image_url(banner):
    return reverse('conteudo:image', args=[banner.pk])


class BannerSerializer(StrictPayloadMixin, serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    titulo = serializers.CharField(max_length=150)
    texto_alternativo = serializers.CharField(max_length=250, required=False, allow_blank=True)
    banner_img = serializers.FileField(write_only=True, required=False)
    imagem_url = serializers.SerializerMethodField()
    status = serializers.ChoiceField(choices=StatusBanner.choices)
    local = serializers.ChoiceField(choices=LocalBanner.choices)
    ordem = StrictIntegerField(min_value=0, max_value=2147483647, required=False)
    inicio_exibicao = AwareDateTimeField(required=False, allow_null=True)
    fim_exibicao = AwareDateTimeField(required=False, allow_null=True)
    versao = StrictIntegerField(min_value=1, max_value=9223372036854775806, required=False)

    def get_imagem_url(self, obj):
        return image_url(obj)

    def validate(self, attrs):
        if self.instance is None:
            if 'versao' in attrs:
                raise serializers.ValidationError({'versao': 'A versão inicial é definida pelo sistema.'})
            if 'banner_img' not in attrs:
                raise serializers.ValidationError({'banner_img': 'Envie uma imagem WebP.'})
        elif 'versao' not in attrs:
            raise serializers.ValidationError({'versao': 'Informe a versão do banner.'})
        return attrs

    def _save(self, data, instance=None):
        image = data.pop('banner_img', None)
        version = data.pop('versao', None)
        try:
            return save_banner(actor=self.context['request'].user, data=data, image=image,
                               banner_id=instance.pk if instance else None, expected_version=version)
        except ValidationError as error:
            raise serializers.ValidationError(error.message_dict if hasattr(error, 'message_dict')
                                              else {'non_field_errors': error.messages}) from error

    def create(self, validated_data):
        return self._save(validated_data)

    def update(self, instance, validated_data):
        return self._save(validated_data, instance)


class DeleteBannerSerializer(StrictPayloadMixin, serializers.Serializer):
    versao = StrictIntegerField(min_value=1, max_value=9223372036854775806)


class PublicBannerSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    titulo = serializers.CharField(read_only=True)
    texto_alternativo = serializers.SerializerMethodField()
    imagem_url = serializers.SerializerMethodField()
    local = serializers.CharField(read_only=True)
    ordem = serializers.IntegerField(read_only=True)

    def get_texto_alternativo(self, obj):
        return obj.texto_alternativo or obj.titulo

    def get_imagem_url(self, obj):
        return image_url(obj)
