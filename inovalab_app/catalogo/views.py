from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import FileResponse, Http404, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.generic import CreateView, DetailView, ListView, UpdateView, View

from inovalab_app.adapters.host import is_business_admin
from inovalab_app.catalogo.services import save_entry
from inovalab_app.catalogo.models import Equipamento


class CatalogContextMixin:
    category = ''

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'category': self.category,
            'title': self.model._meta.verbose_name_plural,
            'singular_title': self.model._meta.verbose_name,
            'can_manage': is_business_admin(self.request.user),
            'list_url': reverse(f'catalogo:{self.category}-list'),
            'create_url': reverse(f'catalogo:{self.category}-create'),
            'detail_url_name': f'catalogo:{self.category}-detail',
            'update_url_name': f'catalogo:{self.category}-update',
        })
        return context


class BusinessAdminRequiredMixin:
    def dispatch(self, request, *args, **kwargs):
        if not is_business_admin(request.user):
            raise PermissionDenied('Somente administradores do laboratório podem manter o catálogo.')
        return super().dispatch(request, *args, **kwargs)


class CatalogListView(LoginRequiredMixin, CatalogContextMixin, ListView):
    template_name = 'inovalab_app/catalogo/list.html'
    paginate_by = 25


class CatalogDetailView(LoginRequiredMixin, CatalogContextMixin, DetailView):
    template_name = 'inovalab_app/catalogo/detail.html'


class CatalogWriteMixin(CatalogContextMixin):
    template_name = 'inovalab_app/catalogo/form.html'

    def form_valid(self, form):
        try:
            self.object = save_entry(
                actor=self.request.user, model=self.model,
                data=form.cleaned_data, instance=self.object,
            )
        except ValidationError as error:
            errors = error.message_dict if hasattr(error, 'message_dict') else {'__all__': error.messages}
            for field, field_errors in errors.items():
                form.add_error(field if field in form.fields else None, field_errors)
            return self.form_invalid(form)
        messages.success(self.request, 'Cadastro salvo com sucesso.')
        return HttpResponseRedirect(reverse(f'catalogo:{self.category}-detail', args=[self.object.pk]))


class CatalogCreateView(LoginRequiredMixin, BusinessAdminRequiredMixin, CatalogWriteMixin, CreateView):
    pass


class CatalogUpdateView(LoginRequiredMixin, BusinessAdminRequiredMixin, CatalogWriteMixin, UpdateView):
    pass


class EquipmentPhotoView(LoginRequiredMixin, View):
    def get(self, request):
        name = request.GET.get('arquivo', '')
        if not name:
            raise Http404
        equipment = get_object_or_404(Equipamento, foto=name)
        try:
            stream = equipment.foto.open('rb')
        except OSError as error:
            raise Http404 from error
        response = FileResponse(stream)
        response['X-Content-Type-Options'] = 'nosniff'
        return response
