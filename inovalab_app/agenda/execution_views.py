from copy import copy
from urllib.parse import urlsplit

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.http import QueryDict
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.cache import never_cache

from inovalab_app.agenda.forms import VisitRealizeForm
from inovalab_app.agenda.services import BookingConflict, mark_visit_realized
from inovalab_app.agenda.views import AdminAgendaAccessMixin, BookingReviewListView


def safe_realization_return(request, value, booking):
    fallback = booking.get_absolute_url()
    try:
        parts = urlsplit(value or '')
    except ValueError:
        return fallback
    if parts.scheme or parts.netloc:
        return fallback
    if parts.path == fallback:
        return fallback
    if parts.path != reverse('agenda:requests'):
        return fallback
    parameters = QueryDict(parts.query)
    selected = QueryDict('', mutable=True)
    for key in ('q', 'mes', 'status', 'execucao', 'page'):
        if key in parameters:
            selected[key] = parameters.get(key)
    copied = copy(request)
    copied.GET = selected
    view = BookingReviewListView()
    view.setup(copied)
    try:
        rows = view.get_queryset()
    except ValidationError:
        return fallback
    if 'page' in selected:
        selected['page'] = str(Paginator(rows, view.paginate_by).get_page(selected['page']).number)
    query = selected.urlencode()
    return parts.path + ('?' + query if query else '')


@method_decorator(never_cache, name='dispatch')
class VisitRealizeView(AdminAgendaAccessMixin, View):
    http_method_names = ['post', 'options']

    def post(self, request, pk):
        form = VisitRealizeForm(request.POST)
        booking = self.get_visit(pk)
        status, message = 400, 'Confira a versão e os campos enviados.'
        if form.is_valid():
            try:
                saved = mark_visit_realized(actor=request.user, booking_id=pk,
                                           expected_version=form.cleaned_data['versao'])
            except BookingConflict as error:
                status, message = 409, str(error)
            except ValidationError as error:
                message = ' '.join(error.messages)
            else:
                messages.success(request, 'Realização da visita registrada. Histórico preservado.')
                return redirect(safe_realization_return(request, form.cleaned_data['retorno'], saved))
        return render(request, 'inovalab_app/agenda/error.html', {'booking': booking, 'message': message}, status=status)

    def get_visit(self, pk):
        from inovalab_app.agenda.selectors import visible_booking
        return visible_booking(self.request.user, 'visita', pk)
