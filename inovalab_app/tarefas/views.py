from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DetailView, ListView, UpdateView, View

from inovalab_app.adapters.host import is_business_admin
from inovalab_app.catalogo.models import Servico
from inovalab_app.tarefas.forms import DeleteForm, ServiceConfirmationTaskForm, TaskForm, TransitionForm
from inovalab_app.tarefas.modal import render_task_form, task_saved
from inovalab_app.tarefas.models import StatusTarefa, Tarefa
from inovalab_app.tarefas.selectors import visible_tasks
from inovalab_app.tarefas.services import PUBLIC_FIELDS, TaskConflict, allowed_actions, delete_task, save_task, transition_task, set_task_status, allowed_statuses


class TaskContextMixin:
    def get_queryset(self):
        return visible_tasks(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['can_manage'] = is_business_admin(self.request.user)
        return context


class AdminRequiredMixin:
    def dispatch(self, request, *args, **kwargs):
        if not is_business_admin(request.user):
            if 'pk' in kwargs:
                get_object_or_404(visible_tasks(request.user), pk=kwargs['pk'])
            raise PermissionDenied('Somente administradores do laboratório podem gerenciar tarefas.')
        return super().dispatch(request, *args, **kwargs)


class TaskBoardView(LoginRequiredMixin, TaskContextMixin, ListView):
    model = Tarefa
    template_name = 'inovalab_app/tarefas/board.html'
    paginate_by = 25

    def filtered_tasks(self):
        queryset = super().get_queryset()
        self.query = self.request.GET.get('q', '').strip()[:150]
        value = self.request.GET.get('servico', '')
        self.selected_service = value if value.isascii() and value.isdecimal() and len(value) <= 12 else ''
        if self.query:
            queryset = queryset.filter(Q(descricao__icontains=self.query) | Q(agendamento_servico__servico__titulo__icontains=self.query)
                                       | Q(responsaveis__username__icontains=self.query)
                                       | Q(responsaveis__first_name__icontains=self.query)).distinct()
        if self.selected_service:
            queryset = queryset.filter(agendamento_servico__servico_id=self.selected_service)
        return queryset

    def get_queryset(self):
        queryset = self.filtered_tasks()
        self.selected_status = self.request.GET.get('status', '')
        if self.selected_status not in StatusTarefa.values:
            self.selected_status = ''
        return queryset.filter(status=self.selected_status) if self.selected_status else queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        counts = dict(self.get_queryset().order_by().values('status').annotate(total=Count('pk', distinct=True)).values_list('status', 'total'))
        for task in context['object_list']:
            destinations = allowed_statuses(self.request.user, task)
            task.move_choices = [(value, label) for value, label in StatusTarefa.choices
                                 if value != task.status and value in destinations]
        context['columns'] = [
            {'label': label, 'status': status, 'count': counts.get(status, 0),
             'tasks': [task for task in context['object_list'] if task.status == status]}
            for status, label in StatusTarefa.choices
        ]
        totals = dict(self.filtered_tasks().order_by().values('status').annotate(total=Count('pk', distinct=True)).values_list('status', 'total'))
        context.update(stat_counts={status: totals.get(status, 0) for status in StatusTarefa.values},
                       query=self.query, selected_service=self.selected_service, selected_status=self.selected_status,
                       services=Servico.objects.filter(pk__in=visible_tasks(self.request.user).values(
                           'agendamento_servico__servico_id')).order_by('titulo', 'pk'), statuses=StatusTarefa.choices)
        return context


class TaskDetailView(LoginRequiredMixin, TaskContextMixin, DetailView):
    model = Tarefa
    context_object_name = 'task'
    template_name = 'inovalab_app/tarefas/detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_form'] = TransitionForm(initial={'status': self.object.status, 'versao': self.object.versao})
        context['status_form'].fields['status'].widget.allowed_values = allowed_statuses(self.request.user, self.object)
        context['can_transition'] = bool(allowed_actions(self.request.user, self.object))
        context['events'] = self.object.eventos.all()[:5]
        context['created_event'] = self.object.eventos.filter(acao='criar').first()
        return context


class TaskWriteMixin(TaskContextMixin):
    model = Tarefa
    form_class = TaskForm
    template_name = 'inovalab_app/tarefas/form.html'

    def render_to_response(self, context, **response_kwargs):
        return render_task_form(
            self.request,
            self.template_name,
            context,
            status=response_kwargs.get('status', 200),
        )

    def post(self, request, *args, **kwargs):
        if 'adicionar_material' in request.POST:
            self.object = self.get_object() if 'pk' in kwargs else None
            data = request.POST.copy()
            try:
                total = int(data.get('materiais-TOTAL_FORMS', '0'))
            except ValueError:
                total = 0
            if 0 <= total < 1000:
                data['materiais-TOTAL_FORMS'] = str(total + 1)
            form = self.form_class(data=data, instance=self.object)
            return self.render_to_response(self.get_context_data(form=form))
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        creating = self.object is None
        try:
            self.object = save_task(
                actor=self.request.user, task_id=self.object.pk if self.object else None,
                data={key: form.cleaned_data[key] for key in PUBLIC_FIELDS if key in form.cleaned_data},
                expected_version=form.cleaned_data.get('versao'),
            )
        except TaskConflict as error:
            form.add_error(None, str(error))
            response = self.form_invalid(form)
            response.status_code = 409
            return response
        except ValidationError as error:
            for field, errors in error.message_dict.items():
                form.add_error(field if field in form.fields else None, errors)
            return self.form_invalid(form)
        return task_saved(self.request, self.object, creating=creating)


class TaskCreateView(LoginRequiredMixin, AdminRequiredMixin, TaskWriteMixin, CreateView):
    pass


class TaskUpdateView(LoginRequiredMixin, AdminRequiredMixin, TaskWriteMixin, UpdateView):
    pass


class ServiceConfirmationTaskView(LoginRequiredMixin, View):
    def get_booking(self, request, pk):
        from inovalab_app.agenda.models import AgendaServico
        if not is_business_admin(request.user):
            raise PermissionDenied('Somente administradores podem confirmar serviços e criar tarefas.')
        return get_object_or_404(AgendaServico.objects.select_related('servico', 'criado_por'),
                                 pk=pk, cancelado_em__isnull=True)

    def render_form(self, request, booking, form, *, status=200, confirmation_error=''):
        return render_task_form(request, 'inovalab_app/tarefas/form.html', {
            'form': form, 'object': None, 'confirmation_booking': booking,
            'confirmation_error': confirmation_error,
        }, status=status)

    def get(self, request, pk):
        booking = self.get_booking(request, pk)
        form = ServiceConfirmationTaskForm(booking=booking)
        if booking.situacao != 'pendente':
            return self.render_form(request, booking, form, status=409,
                confirmation_error='Esta solicitação já foi avaliada. Consulte os dados atualizados.')
        return self.render_form(request, booking, form)

    def post(self, request, pk):
        from inovalab_app.agenda.services import BookingConflict, review_booking
        booking = self.get_booking(request, pk)
        data = request.POST.copy()
        if 'adicionar_material' in data:
            try:
                total = int(data.get('materiais-TOTAL_FORMS', '0'))
            except ValueError:
                total = 0
            if 0 <= total < 1000:
                data['materiais-TOTAL_FORMS'] = str(total + 1)
            return self.render_form(request, booking, ServiceConfirmationTaskForm(data, booking=booking))
        form = ServiceConfirmationTaskForm(data, booking=booking)
        if not form.is_valid():
            return self.render_form(request, booking, form, status=400)
        try:
            saved = review_booking(actor=request.user, category='servico', booking_id=pk,
                expected_version=form.cleaned_data['agendamento_versao'], decision='aprovar',
                task_data={key: form.cleaned_data[key] for key in PUBLIC_FIELDS - {'agendamento_servico'}
                           if key in form.cleaned_data})
        except BookingConflict as error:
            form.add_error(None, str(error))
            return self.render_form(request, booking, form, status=409)
        except ValidationError as error:
            errors = error.message_dict if hasattr(error, 'message_dict') else {None: error.messages}
            for field, values in errors.items():
                form.add_error(field if field in form.fields else None, values)
            return self.render_form(request, booking, form, status=400)
        if request.headers.get('X-Task-Modal') == '1':
            from django.http import JsonResponse
            response = JsonResponse({'saved': True, 'message': 'Tarefa criada e agendamento confirmado.',
                'detail_url': reverse('tarefas:detail', kwargs={'pk': saved.created_task.pk})}, status=201)
            response['Cache-Control'] = 'no-store'
            return response
        messages.success(request, 'Tarefa criada e agendamento confirmado.')
        return redirect('agenda:detail', category='servico', pk=pk)


def operation_error(request, task, message, status=400):
    return render(request, 'inovalab_app/tarefas/error.html', {'task': task, 'message': message}, status=status)


@login_required
@require_POST
def transition_view(request, pk):
    task = get_object_or_404(visible_tasks(request.user), pk=pk)
    form = TransitionForm(request.POST)
    if not form.is_valid():
        return operation_error(request, task, 'Confira a ação, a versão e os campos enviados.')
    try:
        set_task_status(actor=request.user, task_id=pk, status=form.cleaned_data['status'],
                        expected_version=form.cleaned_data['versao'])
    except TaskConflict as error:
        return operation_error(request, task, str(error), 409)
    except ValidationError as error:
        return operation_error(request, task, ' '.join(error.messages))
    messages.success(request, 'Status da tarefa atualizado.')
    return redirect('tarefas:detail', pk=pk)


class TaskDeleteView(LoginRequiredMixin, AdminRequiredMixin, View):
    def get(self, request, pk):
        task = get_object_or_404(visible_tasks(request.user), pk=pk)
        return render(request, 'inovalab_app/tarefas/delete.html', {'task': task, 'form': DeleteForm(initial={'versao': task.versao})})

    def post(self, request, pk):
        task = get_object_or_404(visible_tasks(request.user), pk=pk)
        form = DeleteForm(request.POST)
        if not form.is_valid():
            return operation_error(request, task, 'Informe a versão válida da tarefa.')
        try:
            delete_task(actor=request.user, task_id=pk, expected_version=form.cleaned_data['versao'])
        except TaskConflict as error:
            return operation_error(request, task, str(error), 409)
        messages.success(request, 'Tarefa excluída. O histórico foi preservado.')
        return redirect('tarefas:board')


class TaskHistoryView(LoginRequiredMixin, ListView):
    template_name = 'inovalab_app/tarefas/history.html'
    paginate_by = 25

    def get_queryset(self):
        self.task = get_object_or_404(visible_tasks(self.request.user), pk=self.kwargs['pk'])
        return self.task.eventos.all()

    def get_context_data(self, **kwargs):
        return {**super().get_context_data(**kwargs), 'task': self.task}
