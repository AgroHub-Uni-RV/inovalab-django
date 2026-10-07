from rest_framework.permissions import BasePermission, SAFE_METHODS

from inovalab_app.adapters.host import is_business_admin


class CanMaintainCatalog(BasePermission):
    message = 'Somente administradores do laboratório podem manter o catálogo.'

    def has_permission(self, request, view):
        return request.method in SAFE_METHODS or is_business_admin(request.user)
