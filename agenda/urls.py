from django.urls import path

from agenda import views, remote_views, personal

app_name = 'agenda'
urlpatterns = [
    path('', views.BookingListView.as_view(), name='list'),
    path('meus/', personal.MyBookingsListView.as_view(), name='mine'),
    path('meus/visitas/<int:pk>/', personal.MyBookingDetailView.as_view(), name='my-visit-detail'),
    path('meus/<str:category>/<int:pk>/', personal.MyBookingDetailView.as_view(), name='my-detail'),
    path('visitas/', personal.MyBookingsListView.as_view(), name='visit-list'),
    path('visitas/novo/', remote_views.RemoteBookingWriteView.as_view(), name='visit-create'),
    path('visitas/<int:pk>/', remote_views.RemoteBookingDetailView.as_view(), name='visit-detail'),
    path('visitas/<int:pk>/editar/', remote_views.RemoteBookingWriteView.as_view(), name='visit-update'),
    path('visitas/<int:pk>/cancelar/', remote_views.RemoteBookingCancelView.as_view(), name='visit-cancel'),
    path('novo/', views.BookingWriteView.as_view(), name='create'),
    path('solicitacoes/', views.BookingReviewListView.as_view(), name='requests'),
    path('solicitacoes/<int:pk>/decidir/', views.RemoteBookingDecisionView.as_view(), name='remote-decision'),
    path('<str:category>/<int:pk>/avaliar/', views.BookingReviewView.as_view(), name='review'),
    path('<str:category>/<int:pk>/', views.BookingDetailView.as_view(), name='detail'),
    path('<str:category>/<int:pk>/criador/foto/', views.BookingCreatorPhotoView.as_view(), name='creator-photo'),
    path('<str:category>/<int:pk>/editar/', views.BookingWriteView.as_view(), name='update'),
    path('<str:category>/<int:pk>/cancelar/', views.BookingCancelView.as_view(), name='cancel'),
    path('<str:category>/<int:pk>/historico/', views.BookingHistoryView.as_view(), name='history'),
]
