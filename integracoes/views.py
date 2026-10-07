from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.generic import DetailView, ListView, View

from accounts.policies import is_business_admin
from agenda.services import BookingConflict
from integracoes.forms import ClientCreateForm, ClientUpdateForm, CredentialForm
from integracoes.models import ClienteIntegracao
from integracoes.selectors import visible_clients
from integracoes.services import create_client, rotate_credential, update_client


class IntegrationAccessMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not is_business_admin(request.user):
            raise PermissionDenied('Somente administradores do laboratório podem gerenciar integrações.')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return visible_clients(self.request.user)


def secret_response(request, client, token):
    response = render(request, 'integracoes/secret.html', {'integration': client, 'token': token})
    response['Cache-Control'] = 'no-store, private'
    response['Referrer-Policy'] = 'no-referrer'
    return response


def form_error(form, error):
    details = error.message_dict if hasattr(error, 'message_dict') else {None: error.messages}
    for field, errors in details.items():
        form.add_error(field if field in form.fields else None, errors)


class ClientListView(IntegrationAccessMixin, ListView):
    template_name = 'integracoes/list.html'
    paginate_by = 25


class ClientDetailView(IntegrationAccessMixin, DetailView):
    model = ClienteIntegracao
    context_object_name = 'integration'
    template_name = 'integracoes/detail.html'


class ClientWriteView(IntegrationAccessMixin, View):
    def get_integration(self):
        return get_object_or_404(self.get_queryset(), pk=self.kwargs['pk']) if 'pk' in self.kwargs else None

    def get(self, request, **kwargs):
        client = self.get_integration()
        form = ClientUpdateForm(initial={'nome': client.nome, 'ativo': client.ativo, 'versao': client.versao}) if client else ClientCreateForm()
        return render(request, 'integracoes/form.html', {'form': form, 'integration': client})

    def post(self, request, **kwargs):
        client = self.get_integration()
        form = ClientUpdateForm(request.POST) if client else ClientCreateForm(request.POST)
        status = 200
        if form.is_valid():
            try:
                if client:
                    update_client(actor=request.user, client_id=client.pk, expected_version=form.cleaned_data['versao'],
                                  data={key: form.cleaned_data[key] for key in ('nome', 'ativo')})
                else:
                    created, token = create_client(actor=request.user, name=form.cleaned_data['nome'])
                    return secret_response(request, created, token)
            except BookingConflict as error:
                form.add_error(None, str(error))
                status = 409
            except ValidationError as error:
                form_error(form, error)
            else:
                messages.success(request, 'Integrador atualizado.')
                return redirect('integracoes:detail', pk=client.pk)
        return render(request, 'integracoes/form.html', {'form': form, 'integration': client}, status=status)


class CredentialView(IntegrationAccessMixin, View):
    def get(self, request, pk):
        client = get_object_or_404(self.get_queryset(), pk=pk)
        return render(request, 'integracoes/credential.html', {'integration': client, 'form': CredentialForm(initial={'versao': client.versao})})

    def post(self, request, pk):
        client = get_object_or_404(self.get_queryset(), pk=pk)
        form = CredentialForm(request.POST)
        status = 400
        if form.is_valid():
            try:
                client, token = rotate_credential(actor=request.user, client_id=pk, expected_version=form.cleaned_data['versao'])
            except BookingConflict as error:
                form.add_error(None, str(error))
                status = 409
            except ValidationError as error:
                form_error(form, error)
            else:
                return secret_response(request, client, token)
        return render(request, 'integracoes/credential.html', {'integration': client, 'form': form}, status=status)


class ClientRequestsView(IntegrationAccessMixin, ListView):
    template_name = 'integracoes/requests.html'
    paginate_by = 25

    def get_queryset(self):
        self.integration = get_object_or_404(visible_clients(self.request.user), pk=self.kwargs['pk'])
        return self.integration.pedidos.select_related('agenda_servico', 'agenda_equipamento').all()

    def get_context_data(self, **kwargs):
        return {**super().get_context_data(**kwargs), 'integration': self.integration}
