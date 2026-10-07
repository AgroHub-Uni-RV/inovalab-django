from django.core.exceptions import PermissionDenied, ValidationError
from django.views import View

from accounts.policies import is_business_admin
from agenda.modal import booking_saved, render_booking
from agenda.services import BookingConflict, VISIT_FIELDS, save_booking
from agenda.views import BookingWriteAccessMixin
from agenda.visit_forms import VisitForm


class VisitWriteView(BookingWriteAccessMixin, View):
    def get_booking(self):
        if 'pk' not in self.kwargs:
            return None
        if not is_business_admin(self.request.user):
            raise PermissionDenied
        self.kwargs['category'] = 'visita'
        return self.get_object()

    def get(self, request, **kwargs):
        booking = self.get_booking()
        return render_booking(request, 'agenda/visit_form.html', {'booking': booking, 'form': VisitForm(booking=booking)})

    def post(self, request, **kwargs):
        booking = self.get_booking()
        form = VisitForm(request.POST, booking=booking)
        status = 200
        if form.is_valid():
            try:
                saved = save_booking(actor=request.user, category='visita',
                    booking_id=booking.pk if booking else None, expected_version=form.cleaned_data['versao'],
                    data={**{key: value for key, value in form.cleaned_data.items() if key in VISIT_FIELDS},
                          'categoria': 'visita'})
            except BookingConflict as error:
                form.add_error(None, str(error))
                status = 409
            except ValidationError as error:
                for name, errors in error.message_dict.items():
                    form.add_error(name if name in form.fields else None, errors)
            else:
                return booking_saved(request, saved, creating=booking is None)
        return render_booking(request, 'agenda/visit_form.html', {'booking': booking, 'form': form}, status=status)
