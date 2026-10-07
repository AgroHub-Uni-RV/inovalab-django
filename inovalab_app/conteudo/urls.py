from django.urls import path

from inovalab_app.conteudo import views
from inovalab_app.conteudo import institucional

app_name = 'conteudo'
urlpatterns = [
    path('', institucional.inicio, name='inicio'),
    path('sobre/', institucional.sobre, name='sobre'),
    path('servicos/', institucional.servicos, name='servicos'),
    path('contato/', institucional.contato, name='contato'),
    path('regimento/', institucional.regimento, name='regimento'),
    path('calendario-de-funcionamento/', institucional.calendario_funcionamento, name='calendario-funcionamento'),
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
