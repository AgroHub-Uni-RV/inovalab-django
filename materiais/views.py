from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods
from django.views.generic import DetailView, ListView

from accounts.policies import is_business_admin
from materiais.forms import MaterialCreateForm, MaterialUpdateForm
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
