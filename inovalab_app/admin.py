from django.contrib import admin
from inovalab_app.models import (AgendaEquipamento, AgendaServico, AgendaVisita, Banner,
                                Equipamento, EventoAgendamento, EventoTarefa, Material, Servico, Tarefa)

for model in (Material, EventoTarefa,
              AgendaVisita, EventoAgendamento, Banner):
    admin.site.register(model)


@admin.register(AgendaServico)
class ServiceBookingAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        # Native creation/confirmation must include a task and both audit trails.
        return False


@admin.register(Equipamento)
class EquipmentAdmin(admin.ModelAdmin):
    def get_queryset(self, request):
        return super().get_queryset(request).filter(excluido_em__isnull=True)

    def delete_model(self, request, obj):
        from django.utils import timezone
        obj.excluido_em = timezone.now()
        obj.save(update_fields=['excluido_em'])

    def delete_queryset(self, request, queryset):
        from django.utils import timezone
        queryset.update(excluido_em=timezone.now())

    def get_deleted_objects(self, objs, request):
        # Logical deletion changes only these rows; protected references survive.
        objects = list(objs)
        return ([str(obj) for obj in objects],
                {self.model._meta.verbose_name_plural: len(objects)}, set(), [])


@admin.register(Tarefa)
class TaskAdmin(admin.ModelAdmin):
    """Operational writes go through the task workflow, including its audit trail."""
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
