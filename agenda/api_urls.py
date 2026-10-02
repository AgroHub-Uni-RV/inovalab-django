from rest_framework.routers import DefaultRouter

from agenda.api import BookingViewSet

router = DefaultRouter()
router.register('agendamentos', BookingViewSet, basename='agendamentos')
urlpatterns = router.urls
