from django import forms

from inovalab_app.catalogo.initial_resources import INITIAL_EQUIPMENT




class EquipmentOptionsMixin:
    template_name = 'inovalab_app/agenda/widgets/equipment.html'
    option_template_name = 'inovalab_app/agenda/widgets/equipment_option.html'

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex, attrs)
        if hasattr(value, 'instance'):
            equipment = value.instance
            option.update(photo_url=equipment.foto.url if equipment.foto else '', description=equipment.descricao,
                          code=equipment.codigo_inicial, unavailable=equipment.status == 'indisponivel')
        return option

    def optgroups(self, name, value, attrs=None):
        groups = super().optgroups(name, value, attrs)
        order = {item[0]: index for index, item in enumerate(INITIAL_EQUIPMENT)}
        return sorted(groups, key=lambda group: order.get(group[1][0].get('code'), len(order)))


class EquipmentRadioSelect(EquipmentOptionsMixin, forms.RadioSelect):
    pass


class EquipmentCheckboxSelectMultiple(EquipmentOptionsMixin, forms.CheckboxSelectMultiple):
    pass
