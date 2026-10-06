from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Count, Q
from django.http import FileResponse, Http404, HttpResponseNotFound
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_safe
from django.views.generic import DetailView, ListView

from accounts.policies import is_business_admin
from conteudo.forms import BannerForm, DeleteBannerForm
from conteudo.models import StatusBanner
from conteudo.selectors import published_banners, visible_banners
from conteudo.services import BannerConflict, delete_banner, save_banner


def require_admin(user):
    if not is_business_admin(user):
        raise PermissionDenied('Somente administradores do laboratório podem administrar banners.')


class BannerContextMixin:
    def get_queryset(self):
        require_admin(self.request.user)
        return visible_banners(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['category'] = 'banners'
        return context


@method_decorator(never_cache, name='dispatch')
class BannerListView(LoginRequiredMixin, BannerContextMixin, ListView):
    template_name = 'conteudo/list.html'
    paginate_by = 25

    def filtered_banners(self):
        queryset = super().get_queryset()
        self.query = self.request.GET.get('q', '').strip()[:150]
        if self.query:
            queryset = queryset.filter(Q(titulo__icontains=self.query) | Q(texto_alternativo__icontains=self.query))
        return queryset

    def get_queryset(self):
        queryset = self.filtered_banners()
        status = self.request.GET.get('status', '')
        self.selected_status = status if status in StatusBanner.values else ''
        return queryset.filter(status=self.selected_status) if self.selected_status else queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(query=self.query, selected_status=self.selected_status, statuses=StatusBanner.choices,
                       stat_counts=self.filtered_banners().aggregate(total=Count('pk'),
                           ativo=Count('pk', filter=Q(status='ativo')), inativo=Count('pk', filter=Q(status='inativo')),
                           agendado=Count('pk', filter=Q(status='agendado'))))
        return context


@method_decorator(never_cache, name='dispatch')
class BannerDetailView(LoginRequiredMixin, BannerContextMixin, DetailView):
    template_name = 'conteudo/detail.html'


@never_cache
@login_required
@require_http_methods(['GET', 'POST'])
def banner_form(request, pk=None):
    require_admin(request.user)
    banner = get_object_or_404(visible_banners(request.user), pk=pk) if pk is not None else None
    form = BannerForm(request.POST if request.method == 'POST' else None,
                      request.FILES if request.method == 'POST' else None, banner=banner)
    response_status = 200
    if request.method == 'POST':
        if form.is_valid():
            data = dict(form.cleaned_data)
            image = data.pop('banner_img', None)
            version = data.pop('versao', None)
            try:
                saved = save_banner(actor=request.user, data=data, image=image,
                                   banner_id=pk, expected_version=version)
            except BannerConflict as error:
                form.add_error(None, str(error))
                response_status = 409
            except ValidationError as error:
                errors = error.message_dict if hasattr(error, 'message_dict') else {'__all__': error.messages}
                for field, values in errors.items():
                    form.add_error(field if field in form.fields else None, values)
            else:
                messages.success(request, 'Banner salvo com sucesso.')
                return redirect('conteudo:detail', pk=saved.pk)
        elif banner and 'versao' in form.errors:
            response_status = 400
    return render(request, 'conteudo/form.html', {'form': form, 'object': banner, 'category': 'banners'},
                  status=response_status)


@never_cache
@login_required
@require_http_methods(['GET', 'POST'])
def banner_delete(request, pk):
    require_admin(request.user)
    banner = get_object_or_404(visible_banners(request.user), pk=pk)
    form = DeleteBannerForm(request.POST if request.method == 'POST' else None, initial={'versao': banner.versao})
    response_status = 200
    if request.method == 'POST':
        if form.is_valid():
            try:
                delete_banner(actor=request.user, banner_id=pk, expected_version=form.cleaned_data['versao'])
            except BannerConflict as error:
                form.add_error(None, str(error))
                response_status = 409
            else:
                messages.success(request, 'Banner excluído com sucesso.')
                return redirect('conteudo:list')
        else:
            response_status = 400
    return render(request, 'conteudo/delete.html', {'form': form, 'object': banner, 'category': 'banners'},
                  status=response_status)


@never_cache
@require_safe
def public_page(request, local):
    return render(request, 'conteudo/public.html', {'banners': published_banners(local), 'local': local})


@never_cache
@require_safe
def banner_image(request, pk):
    queryset = visible_banners(request.user) if is_business_admin(request.user) else published_banners()
    try:
        banner = get_object_or_404(queryset, pk=pk)
        stream = banner.banner_img.open('rb')
    except (Http404, OSError):
        response = HttpResponseNotFound('Imagem não encontrada.')
    else:
        response = FileResponse(stream, content_type='image/webp', filename=f'banner-{pk}.webp')
    response['X-Content-Type-Options'] = 'nosniff'
    return response
