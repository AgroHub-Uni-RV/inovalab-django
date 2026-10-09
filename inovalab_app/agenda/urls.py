from django.urls import path

from inovalab_app.agenda import views, visit_views, personal
from inovalab_app.agenda.execution_views import VisitRealizeView

app_name = 'agenda'
urlpatterns = [
    path('meus/<str:category>/<int:pk>/cancelar/', personal.MyBookingCancelView.as_view(), name='my-cancel'),
    path('', views.BookingListView.as_view(), name='list'),
    path('meus/', personal.MyBookingsListView.as_view(), name='mine'),
    path('meus/visitas/<int:pk>/', personal.MyBookingDetailView.as_view(), name='my-visit-detail'),
    path('meus/<str:category>/<int:pk>/', personal.MyBookingDetailView.as_view(), name='my-detail'),
    path('visitas/', personal.MyBookingsListView.as_view(), name='visit-list'),
    path('visitas/novo/', visit_views.VisitWriteView.as_view(), name='visit-create'),
    path('visita/<int:pk>/editar/', visit_views.VisitWriteView.as_view(), name='visit-update'),
    path('novo/', views.BookingWriteView.as_view(), name='create'),
    path('solicitacoes/', views.BookingReviewListView.as_view(), name='requests'),
    path('visita/<int:pk>/realizar/', VisitRealizeView.as_view(), name='visit-realize'),
    path('<str:category>/<int:pk>/avaliar/', views.BookingReviewView.as_view(), name='review'),
    path('<str:category>/<int:pk>/', views.BookingDetailView.as_view(), name='detail'),
    path('<str:category>/<int:pk>/criador/foto/', views.BookingCreatorPhotoView.as_view(), name='creator-photo'),
    path('<str:category>/<int:pk>/editar/', views.BookingWriteView.as_view(), name='update'),
    path('<str:category>/<int:pk>/cancelar/', views.BookingCancelView.as_view(), name='cancel'),
    path('<str:category>/<int:pk>/historico/', views.BookingHistoryView.as_view(), name='history'),
]
