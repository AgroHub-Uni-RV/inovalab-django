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
from agenda.policies import ADMIN_CANCEL_MESSAGE, can_access_agenda, can_create_booking, can_cancel_booking
from agenda.selectors import filter_bookings, visible_bookings, visible_booking, own_booking
from agenda.serializers import BookingSerializer, VisitSerializer, CancelSerializer, EventSerializer
from agenda.services import BookingConflict, cancel_booking


class AgendaPermission(BasePermission):
    message = 'Esta ação exige uma conta ativa com permissão para acessar a agenda.'

    def has_permission(self, request, view):
        if view.action in ('create', 'destroy'):
            return can_create_booking(request.user)
        if view.action in ('update', 'partial_update'):
            return is_business_admin(request.user)
        return can_access_agenda(request.user)

    def has_object_permission(self, request, view, obj):
        if view.action == 'destroy' and is_business_admin(request.user):
            self.message = ADMIN_CANCEL_MESSAGE
        return view.action != 'destroy' or can_cancel_booking(request.user, obj)


class BookingPagination(PageNumberPagination):
    page_size = 25


class BookingViewSet(ModelViewSet):
    authentication_classes = [SessionAuthentication]
    permission_classes = [AgendaPermission]
    renderer_classes = [JSONRenderer]
    pagination_class = BookingPagination
    serializer_class = BookingSerializer
    http_method_names = ['get', 'post', 'put', 'patch', 'delete', 'head', 'options']

    def get_serializer_class(self):
        if self.kwargs.get('category') == 'visita' or (
                self.action == 'create' and isinstance(self.request.data, dict) and self.request.data.get('categoria') == 'visita'):
            return VisitSerializer
        return super().get_serializer_class()

    def get_queryset(self):
        queryset = visible_bookings(self.request.user)
        if self.action == 'list':
            return filter_bookings(queryset, month=self.request.query_params.get('mes'),
                                   category=self.request.query_params.get('categoria'),
                                   situation=self.request.query_params.get('situacao'))
        return queryset

    def get_object(self):
        selector = own_booking if self.action == 'destroy' and not is_business_admin(self.request.user) else visible_booking
        booking = selector(self.request.user, self.kwargs['category'], int(self.kwargs['pk']))
        self.check_object_permissions(self.request, booking)
        return booking

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
        saved = cancel_booking(actor=request.user, category=booking.categoria, booking_id=booking.pk, expected_version=payload.validated_data['versao'])
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['get'])
    def historico(self, request, pk=None, category=None):
        page = self.paginate_queryset(self.get_object().eventos.all())
        return self.get_paginated_response(EventSerializer(page, many=True).data)
