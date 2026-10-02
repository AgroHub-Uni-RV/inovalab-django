from django.urls import path

from integracoes.api import ExternalBookingView, ExternalCatalogView

app_name = 'integracoes_api'
urlpatterns = [
    path('agendamentos/', ExternalBookingView.as_view(), name='receive'),
    path('catalogo/', ExternalCatalogView.as_view(), name='catalog'),
]
