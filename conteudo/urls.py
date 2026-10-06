from django.urls import path

from conteudo import views

app_name = 'conteudo'
urlpatterns = [
    path('banners/', views.BannerListView.as_view(), name='list'),
    path('banners/novo/', views.banner_form, name='create'),
    path('banners/<int:pk>/', views.BannerDetailView.as_view(), name='detail'),
    path('banners/<int:pk>/editar/', views.banner_form, name='update'),
    path('banners/<int:pk>/excluir/', views.banner_delete, name='delete'),
    path('banners/<int:pk>/status/', views.banner_status, name='status'),
    path('banners/<int:pk>/imagem/', views.banner_image, name='image'),
    path('publico/', views.public_page, {'local': 'home'}, name='public-home'),
    path('publico/sobre/', views.public_page, {'local': 'sobre'}, name='public-about'),
]
