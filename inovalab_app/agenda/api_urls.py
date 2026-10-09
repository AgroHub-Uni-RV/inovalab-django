from django.urls import path
from inovalab_app.agenda.api import BookingViewSet

urlpatterns = [
    path('agendamentos/', BookingViewSet.as_view({'get': 'list', 'post': 'create'}), name='agendamentos-list'),
    path('agendamentos/<str:category>/<int:pk>/', BookingViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='agendamentos-detail'),
    path('agendamentos/<str:category>/<int:pk>/historico/', BookingViewSet.as_view({'get': 'historico'}), name='agendamentos-historico'),
    path('agendamentos/<str:category>/<int:pk>/confirmar/', BookingViewSet.as_view({'post': 'confirmar'}), name='agendamentos-confirmar'),
    path('agendamentos/<str:category>/<int:pk>/realizar/', BookingViewSet.as_view({'post': 'realizar'}), name='agendamentos-realizar'),
]
