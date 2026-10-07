from rest_framework.authentication import SessionAuthentication
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.renderers import JSONRenderer
from rest_framework.viewsets import ModelViewSet

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
    queryset = Servico.objects.all()
    serializer_class = ServicoSerializer


class EquipamentoViewSet(CatalogViewSet):
    queryset = Equipamento.objects.all()
    serializer_class = EquipamentoSerializer
