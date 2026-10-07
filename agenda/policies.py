from accounts.policies import can_access_panel


def can_access_agenda(actor):
    return bool(actor and can_access_panel(actor))


def can_view_own_bookings(actor):
    return bool(actor and actor.is_authenticated and actor.is_active)
