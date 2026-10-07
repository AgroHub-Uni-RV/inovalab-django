from django.urls import path

from inovalab_app.materiais.views import MaterialDetailView, MaterialListView, material_form


app_name = 'materiais'
urlpatterns = [
    path('', MaterialListView.as_view(), name='list'),
    path('novo/', material_form, name='create'),
    path('<int:pk>/', MaterialDetailView.as_view(), name='detail'),
    path('<int:pk>/editar/', material_form, name='update'),
]
