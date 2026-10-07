from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_safe

from inovalab_app.shared.dashboard import dashboard_context
from inovalab_app.shared.agrohub_events import load_events


@never_cache
@login_required
@require_safe
def dashboard(request):
    events, unavailable = load_events()
    context = dashboard_context(request.user, task_tab=request.GET.get('tarefas'), booking_tab=request.GET.get('agenda'), events=events)
    context['events_unavailable'] = unavailable
    return render(request, 'inovalab_app/shared/dashboard.html', context)
