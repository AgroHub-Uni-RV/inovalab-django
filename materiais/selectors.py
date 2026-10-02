from materiais.models import Material


def visible_materials(actor):
    if not actor.is_authenticated or not actor.is_active:
        return Material.objects.none()
    return Material.objects.all()
