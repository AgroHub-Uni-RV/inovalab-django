from django.urls import path
from django.views.generic import RedirectView

from inovalab_app.catalogo.forms import EquipamentoForm, ServicoForm
from inovalab_app.catalogo.models import Equipamento, Servico
from inovalab_app.catalogo.views import CatalogCreateView, CatalogDetailView, CatalogListView, CatalogUpdateView, EquipmentPhotoView, EquipmentDeleteView


app_name = 'catalogo'


class RetiredServiceRedirect(RedirectView):
    def get_redirect_url(self, *args, **kwargs):
        return super().get_redirect_url()


urlpatterns = [path('', RedirectView.as_view(pattern_name='catalogo:equipamentos-list', permanent=False)),
    path('equipamentos/<int:pk>/excluir/', EquipmentDeleteView.as_view(), name='equipamentos-delete')]
urlpatterns.append(path('equipamentos/foto/', EquipmentPhotoView.as_view(), name='equipment-photo'))

for category, model, form in (
    ('equipamentos', Equipamento, EquipamentoForm),
):
    context = {'model': model, 'category': category}
    urlpatterns.extend([
        path(f'{category}/', CatalogListView.as_view(**context), name=f'{category}-list'),
        path(f'{category}/novo/', CatalogCreateView.as_view(**context, form_class=form), name=f'{category}-create'),
        path(f'{category}/<int:pk>/', CatalogDetailView.as_view(**context), name=f'{category}-detail'),
        path(f'{category}/<int:pk>/editar/', CatalogUpdateView.as_view(**context, form_class=form), name=f'{category}-update'),
    ])

# Links antigos de leitura apontam para o novo fluxo; POST não mantém o catálogo aposentado.
for suffix, name, target in (('', 'list', 'agenda:list'), ('novo/', 'create', 'agenda:create'),
                           ('<int:pk>/', 'detail', 'agenda:list'), ('<int:pk>/editar/', 'update', 'agenda:list')):
    urlpatterns.append(path('servicos/' + suffix, RetiredServiceRedirect.as_view(pattern_name=target), name='servicos-' + name))
