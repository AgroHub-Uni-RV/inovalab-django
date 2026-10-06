from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods
from django.views.generic import DetailView, ListView

from accounts.policies import is_business_admin
from materiais.forms import MaterialCreateForm, MaterialUpdateForm
from materiais.models import StatusMaterial
from materiais.selectors import visible_materials
from materiais.services import MaterialConflict, save_material


class MaterialContextMixin:
    def get_queryset(self):
        return visible_materials(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(category='materiais', can_manage=is_business_admin(self.request.user))
        return context


class MaterialListView(LoginRequiredMixin, MaterialContextMixin, ListView):
    template_name = 'materiais/list.html'
    paginate_by = 25

    def filtered_materials(self):
        queryset = visible_materials(self.request.user)
        self.query = self.request.GET.get('q', '').strip()[:150]
        self.selected_category = self.request.GET.get('categoria', '').strip()[:100]
        if self.query:
            queryset = queryset.filter(Q(nome__icontains=self.query) | Q(categoria__icontains=self.query) |
                                       Q(fonte__icontains=self.query))
        if self.selected_category:
            queryset = queryset.filter(categoria=self.selected_category)
        return queryset

    def get_queryset(self):
        queryset = self.filtered_materials()
        status = self.request.GET.get('status', '')
        self.selected_status = status if status in StatusMaterial.values else ''
        return queryset.filter(status=self.selected_status) if self.selected_status else queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(query=self.query, selected_category=self.selected_category, selected_status=self.selected_status,
                       statuses=StatusMaterial.choices,
                       categories=visible_materials(self.request.user).order_by('categoria').values_list('categoria', flat=True).distinct(),
                       stat_counts=self.filtered_materials().aggregate(total=Count('pk'),
                           disponivel=Count('pk', filter=Q(status='disponivel')),
                           indisponivel=Count('pk', filter=Q(status='indisponivel'))))
        return context


class MaterialDetailView(LoginRequiredMixin, MaterialContextMixin, DetailView):
    template_name = 'materiais/detail.html'


@login_required
@require_http_methods(['GET', 'POST'])
def material_form(request, pk=None):
    if not is_business_admin(request.user):
        raise PermissionDenied('Somente administradores do laboratório podem manter materiais.')
    material = get_object_or_404(visible_materials(request.user), pk=pk) if pk is not None else None
    form_class = MaterialUpdateForm if material else MaterialCreateForm
    form = form_class(request.POST if request.method == 'POST' else None, instance=material,
                      initial={'versao': material.versao} if material else None)
    response_status = 200
    if request.method == 'POST':
        if form.is_valid():
            data = dict(form.cleaned_data)
            version = data.pop('versao', None)
            try:
                saved = save_material(actor=request.user, data=data, material_id=pk, expected_version=version)
            except MaterialConflict as error:
                form.add_error(None, str(error))
                response_status = 409
            except ValidationError as error:
                errors = error.message_dict if hasattr(error, 'message_dict') else {'__all__': error.messages}
                for field, values in errors.items():
                    form.add_error(field if field in form.fields else None, values)
            else:
                messages.success(request, 'Material salvo com sucesso.')
                return redirect('materiais:detail', pk=saved.pk)
        elif material and 'versao' in form.errors:
            response_status = 400
    return render(request, 'materiais/form.html', {'form': form, 'object': material, 'category': 'materiais'},
                  status=response_status)
