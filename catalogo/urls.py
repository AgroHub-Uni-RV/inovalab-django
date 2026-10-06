from django.urls import path
from django.views.generic import RedirectView

from catalogo.forms import EquipamentoForm, EspacoForm, ServicoForm
from catalogo.models import Equipamento, Espaco, Servico
from catalogo.views import CatalogCreateView, CatalogDetailView, CatalogListView, CatalogUpdateView, EquipmentPhotoView


app_name = 'catalogo'
urlpatterns = [path('', RedirectView.as_view(pattern_name='catalogo:servicos-list', permanent=False))]
urlpatterns.append(path('equipamentos/foto/', EquipmentPhotoView.as_view(), name='equipment-photo'))

for category, model, form in (
    ('servicos', Servico, ServicoForm),
    ('equipamentos', Equipamento, EquipamentoForm),
    ('espacos', Espaco, EspacoForm),
):
    context = {'model': model, 'category': category}
    urlpatterns.extend([
        path(f'{category}/', CatalogListView.as_view(**context), name=f'{category}-list'),
        path(f'{category}/novo/', CatalogCreateView.as_view(**context, form_class=form), name=f'{category}-create'),
        path(f'{category}/<int:pk>/', CatalogDetailView.as_view(**context), name=f'{category}-detail'),
        path(f'{category}/<int:pk>/editar/', CatalogUpdateView.as_view(**context, form_class=form), name=f'{category}-update'),
    ])
