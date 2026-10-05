from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_safe

from core.dashboard import dashboard_context


@never_cache
@login_required
@require_safe
def dashboard(request):
    context = dashboard_context(request.user, task_tab=request.GET.get('tarefas'), booking_tab=request.GET.get('agenda'))
    return render(request, 'core/dashboard.html', context)
