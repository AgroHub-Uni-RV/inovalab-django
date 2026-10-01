from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DetailView, ListView, UpdateView, View

from accounts.policies import is_business_admin
from tarefas.forms import ACTION_LABELS, DeleteForm, TaskForm, TransitionForm
from tarefas.models import StatusTarefa, Tarefa
from tarefas.selectors import visible_tasks
from tarefas.services import PUBLIC_FIELDS, TaskConflict, allowed_actions, delete_task, save_task, transition_task


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
    template_name = 'tarefas/board.html'
    paginate_by = 25

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        counts = dict(self.get_queryset().order_by().values('status').annotate(total=Count('pk')).values_list('status', 'total'))
        context['columns'] = [
            {'label': label, 'count': counts.get(status, 0),
             'tasks': [task for task in context['object_list'] if task.status == status]}
            for status, label in StatusTarefa.choices
        ]
        return context


class TaskDetailView(LoginRequiredMixin, TaskContextMixin, DetailView):
    model = Tarefa
    context_object_name = 'task'
    template_name = 'tarefas/detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['actions'] = [{'name': action, 'label': ACTION_LABELS[action]}
                              for action in allowed_actions(self.request.user, self.object)]
        context['events'] = self.object.eventos.all()[:5]
        return context


class TaskWriteMixin(TaskContextMixin):
    model = Tarefa
    form_class = TaskForm
    template_name = 'tarefas/form.html'

    def form_valid(self, form):
        try:
            self.object = save_task(
                actor=self.request.user, task_id=self.object.pk if self.object else None,
                data={key: form.cleaned_data[key] for key in PUBLIC_FIELDS},
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
        messages.success(self.request, 'Tarefa salva com sucesso.')
        return redirect('tarefas:detail', pk=self.object.pk)


class TaskCreateView(LoginRequiredMixin, AdminRequiredMixin, TaskWriteMixin, CreateView):
    pass


class TaskUpdateView(LoginRequiredMixin, AdminRequiredMixin, TaskWriteMixin, UpdateView):
    pass


def operation_error(request, task, message, status=400):
    return render(request, 'tarefas/error.html', {'task': task, 'message': message}, status=status)


@login_required
@require_POST
def transition_view(request, pk):
    task = get_object_or_404(visible_tasks(request.user), pk=pk)
    form = TransitionForm(request.POST)
    if not form.is_valid():
        return operation_error(request, task, 'Confira a ação, a versão e os campos enviados.')
    try:
        transition_task(actor=request.user, task_id=pk, action=form.cleaned_data['acao'],
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
        return render(request, 'tarefas/delete.html', {'task': task, 'form': DeleteForm(initial={'versao': task.versao})})

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
    template_name = 'tarefas/history.html'
    paginate_by = 25

    def get_queryset(self):
        self.task = get_object_or_404(visible_tasks(self.request.user), pk=self.kwargs['pk'])
        return self.task.eventos.all()

    def get_context_data(self, **kwargs):
        return {**super().get_context_data(**kwargs), 'task': self.task}
