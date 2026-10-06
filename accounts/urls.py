from django.contrib.auth.views import LogoutView
from django.urls import path

from accounts.views import AccountLoginView, home, profile_photo
from accounts.user_views import UserListView
from accounts.remote_views import password_reset, password_reset_confirm, register, update_photo


app_name = 'accounts'
urlpatterns = [
    path('', AccountLoginView.as_view(), name='login'),
    path('entrar/', AccountLoginView.as_view(), name='login-alias'),
    path('registro/', register, name='register'),
    path('recuperar-senha/', password_reset, name='password-reset'),
    path('recuperar-senha/confirmar/', password_reset_confirm, name='password-reset-confirm'),
    path('perfil/', home, name='home'),
    path('perfil/foto/', update_photo, name='update-photo'),
    path('usuarios/', UserListView.as_view(), name='users'),
    path('usuarios/<int:pk>/foto/', profile_photo, name='photo'),
    path('sair/', LogoutView.as_view(), name='logout'),
]
