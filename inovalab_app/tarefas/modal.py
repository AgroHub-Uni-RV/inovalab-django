from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.cache import patch_vary_headers


def render_task_form(request, template, context=None, *, status=200):
    context = {**(context or {}), 'form_action': request.path}
    if request.headers.get('X-Task-Modal') == '1':
        context.update(task_modal=True, task_base='inovalab_app/tarefas/modal_base.html')
    response = render(request, template, context, status=status)
    patch_vary_headers(response, ['X-Task-Modal'])
    response['Cache-Control'] = 'no-store'
    return response


def task_saved(request, task, *, creating):
    message = 'Tarefa criada com sucesso.' if creating else 'Tarefa atualizada com sucesso.'
    detail_url = reverse('tarefas:detail', kwargs={'pk': task.pk})
    if request.headers.get('X-Task-Modal') == '1':
        response = JsonResponse({
            'saved': True,
            'message': message,
            'detail_url': detail_url,
        }, status=201 if creating else 200)
        response['Cache-Control'] = 'no-store'
        return response
    messages.success(request, message)
    return redirect(detail_url)
