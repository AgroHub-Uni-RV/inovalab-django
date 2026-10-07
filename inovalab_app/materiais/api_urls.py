from rest_framework.routers import SimpleRouter

from inovalab_app.materiais.api import MaterialViewSet


router = SimpleRouter()
router.register('materiais', MaterialViewSet, basename='material')
urlpatterns = router.urls
