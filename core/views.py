from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_safe

from agenda.views import confirmed_visits
from core.dashboard import dashboard_context
from core.agrohub_events import load_events


@never_cache
@login_required
@require_safe
def dashboard(request):
    events, unavailable = load_events()
    visits, visits_unavailable = confirmed_visits(request)
    context = dashboard_context(request.user, task_tab=request.GET.get('tarefas'), booking_tab=request.GET.get('agenda'), events=events, remote_visits=visits)
    context['visits_unavailable'] = visits_unavailable
    context['events_unavailable'] = unavailable
    return render(request, 'core/dashboard.html', context)
