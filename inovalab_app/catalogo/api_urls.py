from rest_framework.routers import SimpleRouter

from inovalab_app.catalogo.api import EquipamentoViewSet, ServicoViewSet


app_name = 'catalogo_api'
router = SimpleRouter()
router.register('servicos', ServicoViewSet, basename='servico')
router.register('equipamentos', EquipamentoViewSet, basename='equipamento')
urlpatterns = router.urls
