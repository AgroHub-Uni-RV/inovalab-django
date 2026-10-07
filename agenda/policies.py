from accounts.policies import can_access_panel


def can_access_agenda(actor):
    return bool(actor and can_access_panel(actor))
