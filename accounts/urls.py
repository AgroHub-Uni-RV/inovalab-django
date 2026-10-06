from django.contrib.auth.views import LoginView, LogoutView
from django.urls import path

from accounts.views import home


app_name = 'accounts'
urlpatterns = [
    path('', LoginView.as_view(template_name='accounts/login.html', redirect_authenticated_user=True), name='login'),
    path('entrar/', LoginView.as_view(template_name='accounts/login.html', redirect_authenticated_user=True), name='login-alias'),
    path('perfil/', home, name='home'),
    path('sair/', LogoutView.as_view(), name='logout'),
]
