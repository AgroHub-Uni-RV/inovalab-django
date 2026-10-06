from django.contrib.auth.views import LogoutView
from django.urls import path

from accounts.views import AccountLoginView, home, profile_photo
from accounts.user_views import UserListView


app_name = 'accounts'
urlpatterns = [
    path('', AccountLoginView.as_view(), name='login'),
    path('entrar/', AccountLoginView.as_view(), name='login-alias'),
    path('perfil/', home, name='home'),
    path('usuarios/', UserListView.as_view(), name='users'),
    path('usuarios/<int:pk>/foto/', profile_photo, name='photo'),
    path('sair/', LogoutView.as_view(), name='logout'),
]
