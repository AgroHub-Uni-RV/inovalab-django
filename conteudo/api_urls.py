from django.urls import path
from rest_framework.routers import SimpleRouter

from conteudo.api import BannerViewSet, PublicBannerListView

router = SimpleRouter()
router.register('banners', BannerViewSet, basename='banner')
urlpatterns = [path('publico/banners/', PublicBannerListView.as_view(), name='public-banners'), *router.urls]
