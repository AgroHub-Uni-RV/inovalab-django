from django import forms

from catalogo.initial_resources import INITIAL_SPACES


class SpaceRadioSelect(forms.RadioSelect):
    template_name = 'agenda/widgets/spaces.html'
    option_template_name = 'agenda/widgets/space_option.html'

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex, attrs)
        if hasattr(value, 'instance'):
            space = value.instance
            option.update(capacity=space.capacidade_maxima_de_pessoas,
                          restricted=space.somente_administradores,
                          code=space.codigo_inicial,
                          unavailable=space.status == 'indisponivel')
        return option

    def optgroups(self, name, value, attrs=None):
        groups = super().optgroups(name, value, attrs)
        order = {space[0]: index for index, space in enumerate(INITIAL_SPACES)}
        return sorted(groups, key=lambda group: order.get(group[1][0].get('code'), len(order)))
