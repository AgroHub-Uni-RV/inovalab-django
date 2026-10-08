from rest_framework.authentication import SessionAuthentication
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.renderers import JSONRenderer
from rest_framework.viewsets import ModelViewSet
from rest_framework.response import Response
from inovalab_app.catalogo.services import delete_equipment

from inovalab_app.catalogo.models import Equipamento, Servico
from inovalab_app.catalogo.permissions import CanMaintainCatalog
from inovalab_app.catalogo.serializers import EquipamentoSerializer, ServicoSerializer


class CatalogPagination(PageNumberPagination):
    page_size = 25


class CatalogViewSet(ModelViewSet):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated, CanMaintainCatalog]
    renderer_classes = [JSONRenderer]
    pagination_class = CatalogPagination
    http_method_names = ['get', 'post', 'put', 'patch', 'head', 'options']


class ServicoViewSet(CatalogViewSet):
    queryset = Servico.objects.none()
    serializer_class = ServicoSerializer
    http_method_names = ['get', 'head', 'options']

    def list(self, request, *args, **kwargs):
        return Response({'detail': 'Serviços são definidos por solicitação em /api/v1/agendamentos/.'}, status=410)

    retrieve = list


class EquipamentoViewSet(CatalogViewSet):
    queryset = Equipamento.objects.filter(excluido_em__isnull=True)
    serializer_class = EquipamentoSerializer
    http_method_names = ['get', 'post', 'put', 'patch', 'delete', 'head', 'options']

    def destroy(self, request, *args, **kwargs):
        delete_equipment(actor=request.user, equipment_id=self.get_object().pk)
        return Response(status=204)
