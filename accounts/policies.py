from django.contrib.auth.models import AnonymousUser

from accounts.models import User


def is_business_admin(user: User | AnonymousUser) -> bool:
    if not user.is_authenticated or not user.is_active:
        return False
    if user.agrohub_id is not None:
        return 'admin' in user.agrohub_roles
    return user.is_superuser or user.groups.filter(name='Administradores').exists()


def can_access_panel(user: User | AnonymousUser) -> bool:
    if not user.is_authenticated or not user.is_active:
        return False
    if user.agrohub_id is not None:
        return any(role in user.agrohub_roles for role in ('admin', 'staff'))
    # Contas técnicas locais existentes; autenticação de senha continua só no AgroHub.
    return bool(user.is_staff or is_business_admin(user))


def is_technical_admin(user: User | AnonymousUser) -> bool:
    return bool(is_business_admin(user) and user.is_superuser)
