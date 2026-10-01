from django.contrib.auth.models import AnonymousUser

from accounts.models import User


def is_business_admin(user: User | AnonymousUser) -> bool:
    if not user.is_authenticated or not user.is_active:
        return False
    return user.is_superuser or user.groups.filter(name='Administradores').exists()
