from rest_framework.authentication import SessionAuthentication
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import BasePermission, IsAuthenticated, SAFE_METHODS
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from inovalab_app.adapters.host import is_business_admin
from inovalab_app.materiais.parsers import DecimalJSONParser
from inovalab_app.materiais.selectors import visible_materials
from inovalab_app.materiais.serializers import MaterialSerializer
from inovalab_app.materiais.services import MaterialConflict


class CanMaintainMaterials(BasePermission):
    message = 'Somente administradores do laboratório podem manter materiais.'

    def has_permission(self, request, view):
        return request.method in SAFE_METHODS or is_business_admin(request.user)


class MaterialPagination(PageNumberPagination):
    page_size = 25


class MaterialViewSet(ModelViewSet):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated, CanMaintainMaterials]
    parser_classes = [DecimalJSONParser]
    renderer_classes = [JSONRenderer]
    pagination_class = MaterialPagination
    serializer_class = MaterialSerializer
    http_method_names = ['get', 'post', 'put', 'patch', 'head', 'options']

    def get_queryset(self):
        return visible_materials(self.request.user)

    def handle_exception(self, exc):
        if isinstance(exc, MaterialConflict):
            return Response({'detail': str(exc), 'code': 'versao_desatualizada'}, status=409)
        return super().handle_exception(exc)
