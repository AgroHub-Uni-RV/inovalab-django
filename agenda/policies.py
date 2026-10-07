from accounts.policies import can_access_panel, is_business_admin


ADMIN_CANCEL_MESSAGE = 'Administradores podem cancelar somente agendamentos confirmados.'


def can_access_agenda(actor):
    return bool(actor and can_access_panel(actor))


def can_view_own_bookings(actor):
    return bool(actor and actor.is_authenticated and actor.is_active)


def can_create_booking(actor):
    return can_view_own_bookings(actor)


def can_cancel_booking(actor, booking):
    if not can_view_own_bookings(actor) or booking.cancelado_em:
        return False
    if is_business_admin(actor):
        return booking.situacao == 'confirmado'
    return booking.criado_por_id == actor.pk
