def can_access_agenda(actor):
    return bool(actor and actor.is_authenticated and actor.is_active)
