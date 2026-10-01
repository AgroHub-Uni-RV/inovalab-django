from rest_framework.authentication import SessionAuthentication
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.renderers import JSONRenderer
from rest_framework.viewsets import ModelViewSet

from catalogo.models import Equipamento, Espaco, Servico
from catalogo.permissions import CanMaintainCatalog
from catalogo.serializers import EquipamentoSerializer, EspacoSerializer, ServicoSerializer


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


class EspacoViewSet(CatalogViewSet):
    queryset = Espaco.objects.all()
    serializer_class = EspacoSerializer
