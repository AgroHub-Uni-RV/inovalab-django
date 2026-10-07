from django.urls import path

from inovalab_app.shared.views import dashboard

app_name = 'core'
urlpatterns = [path('index/', dashboard, name='dashboard'), path('painel/', dashboard, name='painel')]
