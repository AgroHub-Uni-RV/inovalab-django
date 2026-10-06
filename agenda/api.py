from django.core.exceptions import ValidationError as ModelValidationError
from rest_framework import serializers, status
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import BasePermission
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from accounts.policies import is_business_admin
from agenda.policies import can_access_agenda
from agenda.selectors import filter_bookings, visible_bookings
from agenda.serializers import BookingSerializer, CancelSerializer, EventSerializer
from agenda.services import BookingConflict, cancel_booking
from agenda.agrohub import reservation_summary, sync_reservation
from agenda.models import Agendamento


class AgendaPermission(BasePermission):
    message = 'Esta ação exige uma conta ativa com permissão para acessar a agenda.'

    def has_permission(self, request, view):
        if view.action in ('update', 'partial_update', 'destroy'):
            return is_business_admin(request.user)
        return can_access_agenda(request.user)


class BookingPagination(PageNumberPagination):
    page_size = 25


class BookingViewSet(ModelViewSet):
    authentication_classes = [SessionAuthentication]
    permission_classes = [AgendaPermission]
    renderer_classes = [JSONRenderer]
    pagination_class = BookingPagination
    serializer_class = BookingSerializer
    http_method_names = ['get', 'post', 'put', 'patch', 'delete', 'head', 'options']

    def get_queryset(self):
        if self.action == 'agrohub':
            queryset = Agendamento.objects.filter(reserva_agrohub__isnull=False)
            return queryset if is_business_admin(self.request.user) else queryset.filter(criado_por=self.request.user)
        queryset = visible_bookings(self.request.user).prefetch_related('equipamentos')
        if self.action == 'list':
            return filter_bookings(queryset, month=self.request.query_params.get('mes'),
                                   category=self.request.query_params.get('categoria'),
                                   situation=self.request.query_params.get('situacao'))
        return queryset

    def handle_exception(self, error):
        if isinstance(error, BookingConflict):
            return Response({'detail': str(error), 'code': error.code}, status=409)
        if isinstance(error, ModelValidationError):
            detail = error.message_dict if hasattr(error, 'message_dict') else {'non_field_errors': error.messages}
            if '__all__' in detail:
                detail['non_field_errors'] = detail.pop('__all__')
            error = serializers.ValidationError(detail)
        return super().handle_exception(error)

    def destroy(self, request, *args, **kwargs):
        booking = self.get_object()
        payload = CancelSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        saved = cancel_booking(actor=request.user, booking_id=booking.pk, expected_version=payload.validated_data['versao'], agrohub_request=request)
        remote = reservation_summary(saved)
        if remote and remote['estado'] != 'registrada':
            return Response({'detail': 'Cancelado no InovaLab; confira o resultado no AgroHub.',
                             'reserva_agrohub': remote}, status=202)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['get', 'post'])
    def agrohub(self, request, pk=None):
        booking = self.get_object()
        if request.method == 'POST':
            payload = CancelSerializer(data=request.data)
            payload.is_valid(raise_exception=True)
            if booking.versao != payload.validated_data['versao']:
                raise BookingConflict('versao_desatualizada', 'O agendamento foi alterado. Atualize antes de tentar novamente.')
            sync_reservation(request, booking)
        return Response(reservation_summary(booking))

    @action(detail=True, methods=['get'])
    def historico(self, request, pk=None):
        page = self.paginate_queryset(self.get_object().eventos.all())
        return self.get_paginated_response(EventSerializer(page, many=True).data)
