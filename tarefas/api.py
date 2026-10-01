from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as ModelValidationError
from rest_framework import serializers, status
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from accounts.policies import is_business_admin
from tarefas.selectors import visible_tasks
from tarefas.serializers import DeleteSerializer, EventSerializer, TaskSerializer, TransitionSerializer
from tarefas.services import TaskConflict, delete_task, transition_task


class TaskPagination(PageNumberPagination):
    page_size = 25


class TaskViewSet(ModelViewSet):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]
    renderer_classes = [JSONRenderer]
    pagination_class = TaskPagination
    serializer_class = TaskSerializer
    http_method_names = ['get', 'post', 'put', 'patch', 'delete', 'head', 'options']

    def get_queryset(self):
        return visible_tasks(self.request.user)

    def handle_exception(self, error):
        if isinstance(error, TaskConflict):
            return Response({'detail': str(error), 'code': 'versao_desatualizada'}, status=409)
        if isinstance(error, ModelValidationError):
            detail = error.message_dict if hasattr(error, 'message_dict') else {'non_field_errors': error.messages}
            if '__all__' in detail:
                detail['non_field_errors'] = detail.pop('__all__')
            error = serializers.ValidationError(detail)
        return super().handle_exception(error)

    def require_admin(self):
        if not is_business_admin(self.request.user):
            raise PermissionDenied('Somente administradores do laboratório podem gerenciar tarefas.')

    def create(self, request, *args, **kwargs):
        self.require_admin()
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        self.get_object()
        self.require_admin()
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        task = self.get_object()
        self.require_admin()
        payload = DeleteSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        delete_task(actor=request.user, task_id=task.pk, expected_version=payload.validated_data['versao'])
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post'])
    def transicoes(self, request, pk=None):
        task = self.get_object()
        payload = TransitionSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        task = transition_task(actor=request.user, task_id=task.pk, action=payload.validated_data['acao'],
                               expected_version=payload.validated_data['versao'])
        return Response(self.get_serializer(task).data)

    @action(detail=True, methods=['get'])
    def historico(self, request, pk=None):
        page = self.paginate_queryset(self.get_object().eventos.all())
        return self.get_paginated_response(EventSerializer(page, many=True).data)

    @action(detail=False, methods=['get'])
    def responsaveis(self, request):
        self.require_admin()
        page = self.paginate_queryset(get_user_model().objects.filter(is_active=True).order_by('username', 'pk'))
        return self.get_paginated_response([
            {'id': user.pk, 'username': user.username, 'nome': user.get_full_name() or user.username} for user in page
        ])
