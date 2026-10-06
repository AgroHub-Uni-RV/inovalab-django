from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Exists, OuterRef, Q
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.generic import ListView


@method_decorator(never_cache, name='dispatch')
class UserListView(LoginRequiredMixin, ListView):
    template_name = 'accounts/users.html'
    paginate_by = 15
    http_method_names = ['get', 'head', 'options']

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not (request.user.is_active and request.user.is_superuser):
            raise PermissionDenied('Somente administradores técnicos podem administrar contas.')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        User = get_user_model()
        membership = User.groups.through.objects.filter(user_id=OuterRef('pk'), group__name='Administradores')
        queryset = User.objects.annotate(lab_admin=Exists(membership)).order_by('first_name', 'last_name', 'username', 'pk')
        self.user_counts = queryset.aggregate(total=Count('pk'),
            administradores=Count('pk', filter=Q(is_superuser=True) | Q(lab_admin=True)),
            ativos=Count('pk', filter=Q(is_active=True)), inativos=Count('pk', filter=Q(is_active=False)))
        self.query = self.request.GET.get('q', '').strip()[:150]
        self.selected_tab = self.request.GET.get('tab', 'todos')
        if self.selected_tab not in ('todos', 'administradores', 'ativos', 'inativos'):
            self.selected_tab = 'todos'
        if self.query:
            queryset = queryset.filter(Q(username__icontains=self.query) | Q(first_name__icontains=self.query)
                                       | Q(last_name__icontains=self.query) | Q(email__icontains=self.query))
        if self.selected_tab == 'administradores':
            queryset = queryset.filter(Q(is_superuser=True) | Q(lab_admin=True))
        elif self.selected_tab in ('ativos', 'inativos'):
            queryset = queryset.filter(is_active=self.selected_tab == 'ativos')
        return queryset

    def get_context_data(self, **kwargs):
        return {**super().get_context_data(**kwargs), 'query': self.query, 'selected_tab': self.selected_tab,
                'user_counts': self.user_counts}
