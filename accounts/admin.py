from django.contrib import admin
from django.contrib.auth.admin import GroupAdmin, UserAdmin
from django.contrib.auth.models import Group

from accounts.models import User
from accounts.policies import is_technical_admin


class TechnicalAdminPermissions:
    """Account and privilege management is reserved to technical administrators."""

    def has_module_permission(self, request):
        return is_technical_admin(request.user)

    def has_view_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_add_permission(self, request):
        return self.has_module_permission(request)

    def has_change_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_delete_permission(self, request, obj=None):
        return self.has_module_permission(request)


@admin.register(User)
class TechnicalUserAdmin(TechnicalAdminPermissions, UserAdmin):
    pass


admin.site.unregister(Group)


@admin.register(Group)
class TechnicalGroupAdmin(TechnicalAdminPermissions, GroupAdmin):
    pass


admin.site.site_header = 'InovaLab — Administração'
admin.site.site_title = 'InovaLab'
admin.site.index_title = 'Administração de contas'
