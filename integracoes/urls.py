from django.urls import path

from integracoes import views

app_name = 'integracoes'
urlpatterns = [
    path('', views.ClientListView.as_view(), name='list'),
    path('novo/', views.ClientWriteView.as_view(), name='create'),
    path('<int:pk>/', views.ClientDetailView.as_view(), name='detail'),
    path('<int:pk>/editar/', views.ClientWriteView.as_view(), name='update'),
    path('<int:pk>/credencial/', views.CredentialView.as_view(), name='credential'),
    path('<int:pk>/pedidos/', views.ClientRequestsView.as_view(), name='requests'),
]
