from rest_framework.routers import SimpleRouter

from catalogo.api import EquipamentoViewSet, EspacoViewSet, ServicoViewSet


app_name = 'catalogo_api'
router = SimpleRouter()
router.register('servicos', ServicoViewSet, basename='servico')
router.register('equipamentos', EquipamentoViewSet, basename='equipamento')
router.register('espacos', EspacoViewSet, basename='espaco')
urlpatterns = router.urls
