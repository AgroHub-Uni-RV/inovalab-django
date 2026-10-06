from django.core.exceptions import ValidationError as ModelValidationError
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import JSONParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework.views import APIView

from agenda.services import CATEGORY_MODELS, BookingConflict
from integracoes.authentication import IntegrationAuthentication
from integracoes.credentials import CredentialRejected
from integracoes.serializers import ExternalBookingSerializer
from integracoes.services import receive_booking


class IntegrationAPIView(APIView):
    authentication_classes = [IntegrationAuthentication]
    permission_classes = [IsAuthenticated]
    renderer_classes = [JSONRenderer]
    parser_classes = [JSONParser]

    def handle_exception(self, error):
        if isinstance(error, CredentialRejected):
            error = AuthenticationFailed(str(error))
        if isinstance(error, BookingConflict):
            return Response({'detail': str(error), 'code': error.code}, status=409)
        if isinstance(error, ModelValidationError):
            detail = error.message_dict if hasattr(error, 'message_dict') else {'non_field_errors': error.messages}
            if '__all__' in detail:
                detail['non_field_errors'] = detail.pop('__all__')
            error = serializers.ValidationError(detail)
        return super().handle_exception(error)


class ExternalBookingView(IntegrationAPIView):
    def post(self, request):
        payload = ExternalBookingSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        booking, receipt, repeated = receive_booking(principal=request.auth, data=payload.validated_data)
        return Response({'id': booking.pk, 'id_externo': receipt.id_externo, 'repetido': repeated,
                         'cancelado': booking.cancelado_em is not None, 'versao': booking.versao}, status=200 if repeated else 201)


class CatalogPagination(PageNumberPagination):
    page_size = 25


class ExternalCatalogView(IntegrationAPIView):
    def get(self, request):
        category = request.query_params.get('categoria')
        if category not in CATEGORY_MODELS:
            raise serializers.ValidationError({'categoria': 'Informe servico ou equipamento. Visita não utiliza objeto de catálogo.'})
        queryset = CATEGORY_MODELS[category].objects.exclude(status='indisponivel').order_by('nome', 'pk')
        pagination = CatalogPagination()
        page = pagination.paginate_queryset(queryset, request, view=self)
        return pagination.get_paginated_response([{'id': entry.pk, 'categoria': category, 'nome': entry.nome} for entry in page])
