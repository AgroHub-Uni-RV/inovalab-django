from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db.models import BooleanField, Case, Count, Exists, OuterRef, Q, Value, When
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.generic import ListView
from accounts.policies import is_technical_admin


@method_decorator(never_cache, name='dispatch')
class UserListView(LoginRequiredMixin, ListView):
    template_name = 'accounts/users.html'
    paginate_by = 15
    http_method_names = ['get', 'head', 'options']

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not is_technical_admin(request.user):
            raise PermissionDenied('Somente administradores técnicos podem administrar contas.')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        User = get_user_model()
        membership = User.groups.through.objects.filter(user_id=OuterRef('pk'), group__name='Administradores')
        # /me/ aceita no máximo 20 papéis; índices JSON funcionam em SQLite e PostgreSQL.
        remote_admin = Q()
        for index in range(20):
            remote_admin |= Q(**{f'agrohub_roles__{index}': 'admin'})
        queryset = User.objects.annotate(local_admin_group=Exists(membership)).annotate(lab_admin=Case(
            When(Q(agrohub_id__isnull=False) & remote_admin, then=Value(True)),
            When(Q(agrohub_id__isnull=True) & (Q(is_superuser=True) | Q(local_admin_group=True)), then=Value(True)),
            default=Value(False), output_field=BooleanField(),
        )).order_by('first_name', 'last_name', 'username', 'pk')
        self.user_counts = queryset.aggregate(total=Count('pk'),
            administradores=Count('pk', filter=Q(lab_admin=True)),
            ativos=Count('pk', filter=Q(is_active=True)), inativos=Count('pk', filter=Q(is_active=False)))
        self.query = self.request.GET.get('q', '').strip()[:150]
        self.selected_tab = self.request.GET.get('tab', 'todos')
        if self.selected_tab not in ('todos', 'administradores', 'ativos', 'inativos'):
            self.selected_tab = 'todos'
        if self.query:
            queryset = queryset.filter(Q(username__icontains=self.query) | Q(first_name__icontains=self.query)
                                       | Q(last_name__icontains=self.query) | Q(email__icontains=self.query))
        if self.selected_tab == 'administradores':
            queryset = queryset.filter(lab_admin=True)
        elif self.selected_tab in ('ativos', 'inativos'):
            queryset = queryset.filter(is_active=self.selected_tab == 'ativos')
        return queryset

    def get_context_data(self, **kwargs):
        return {**super().get_context_data(**kwargs), 'query': self.query, 'selected_tab': self.selected_tab,
                'user_counts': self.user_counts}
