from django.contrib import admin
from django.urls import include, path
from accounts.api import MeView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/me/', MeView.as_view(), name='identity-me'),
    path('', include('inovalab_app.urls')),
    path('', include('accounts.urls')),
]
