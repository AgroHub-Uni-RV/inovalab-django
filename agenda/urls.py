from django.urls import path

from agenda import views

app_name = 'agenda'
urlpatterns = [
    path('', views.BookingListView.as_view(), name='list'),
    path('novo/', views.BookingWriteView.as_view(), name='create'),
    path('<int:pk>/', views.BookingDetailView.as_view(), name='detail'),
    path('<int:pk>/criador/foto/', views.BookingCreatorPhotoView.as_view(), name='creator-photo'),
    path('<int:pk>/editar/', views.BookingWriteView.as_view(), name='update'),
    path('<int:pk>/cancelar/', views.BookingCancelView.as_view(), name='cancel'),
    path('<int:pk>/historico/', views.BookingHistoryView.as_view(), name='history'),
]
