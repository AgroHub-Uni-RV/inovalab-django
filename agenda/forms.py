from decimal import Decimal

from django import forms
from django.db.models import Q
from accounts.policies import is_business_admin

from agenda.models import CATEGORIES
from agenda.services import CATEGORY_MODELS, SERVICE_FIELDS
from agenda.widgets import EquipmentCheckboxSelectMultiple, EquipmentRadioSelect, SpaceRadioSelect
from materiais.models import Material


class StrictFormMixin:
    def clean(self):
        cleaned = super().clean()
        if set(self.data) - set(self.fields) - {'csrfmiddlewaretoken'}:
            raise forms.ValidationError('Foram enviados campos que não podem ser alterados.')
        return cleaned


class BookingForm(StrictFormMixin, forms.Form):
    categoria = forms.ChoiceField(label='Categoria', choices=CATEGORIES.items())
    objeto = forms.ModelChoiceField(label='Objeto', queryset=CATEGORY_MODELS['servico'].objects.none())
    requerente = forms.CharField(label='Requerente', max_length=150)
    motivo = forms.CharField(label='Motivo', widget=forms.Textarea(attrs={'rows': 3}))
    inicio = forms.DateTimeField(label='Início', help_text='Horário de Brasília.', widget=forms.DateTimeInput(
        format='%Y-%m-%dT%H:%M:%S', attrs={'type': 'datetime-local', 'step': '1'}))
    fim = forms.DateTimeField(label='Término', widget=forms.DateTimeInput(
        format='%Y-%m-%dT%H:%M:%S', attrs={'type': 'datetime-local', 'step': '1'}))
    equipamentos = forms.ModelMultipleChoiceField(
        label='Equipamentos', queryset=CATEGORY_MODELS['equipamento'].objects.none(), required=False,
        widget=EquipmentCheckboxSelectMultiple, help_text='Selecione as máquinas utilizadas neste serviço (opcional).',
    )
    material_proprio = forms.TypedChoiceField(
        label='Tem material próprio?', choices=[('', 'Selecione'), ('sim', 'Sim'), ('nao', 'Não')],
        coerce=lambda value: value == 'sim', widget=forms.Select(attrs={'data-material-proprio': ''}),
    )
    material_gasto = forms.ModelChoiceField(
        label='Material utilizado', queryset=Material.objects.none(), required=False,
        empty_label='Selecione o material', help_text='Material do laboratório utilizado neste serviço.',
    )
    material_gasto_gramas = forms.DecimalField(
        label='Material gasto (g)', required=False, min_value=Decimal('0.001'), max_digits=12, decimal_places=3,
        widget=forms.NumberInput(attrs={'min': '0.001', 'step': '0.001'}),
        help_text='Informe em gramas o material gasto do laboratório.',
    )
    versao = forms.IntegerField(min_value=1, required=False, widget=forms.HiddenInput)

    def __init__(self, *args, booking=None, actor=None, **kwargs):
        self.booking = booking
        self.actor = actor
        self.is_admin = bool(actor and is_business_admin(actor))
        initial = {}
        if booking:
            initial.update(categoria=booking.categoria, objeto=booking.objeto_id, requerente=booking.requerente,
                           motivo=booking.motivo, inicio=booking.inicio, fim=booking.fim, versao=booking.versao)
            initial.update(equipamentos=list(booking.equipamentos.values_list('pk', flat=True)),
                           material_proprio='sim' if booking.material_proprio is True else
                           'nao' if booking.material_proprio is False else '',
                           material_gasto_gramas=booking.material_gasto_gramas)
            initial['material_gasto'] = booking.material_gasto_id
        initial.update(kwargs.get('initial', {}))
        initial.setdefault('categoria', 'servico')
        kwargs['initial'] = initial
        super().__init__(*args, **kwargs)
        self.fields['categoria'].widget.attrs['data-auto-refresh'] = ''
        category = self.data.get('categoria') if self.is_bound else self.initial['categoria']
        self.category = category
        if category in CATEGORY_MODELS:
            retained_id = booking.objeto_id if booking and category == booking.categoria else None
            self.fields['objeto'].queryset = CATEGORY_MODELS[category].objects.filter(
                ~Q(status='indisponivel') | Q(pk=retained_id),
            ).order_by('nome', 'pk')
            self.fields['objeto'].label = CATEGORIES[category]
            if category == 'espaco':
                self.fields['objeto'].empty_label = None
                self.fields['objeto'].widget = SpaceRadioSelect(
                    choices=self.fields['objeto'].choices, is_admin=self.is_admin,
                )
            elif category == 'equipamento':
                self.fields['objeto'].empty_label = None
                self.fields['objeto'].widget = EquipmentRadioSelect(choices=self.fields['objeto'].choices)
        if category == 'servico':
            self.fields['material_gasto'].queryset = Material.objects.filter(
                ~Q(status='indisponivel') | Q(pk=booking.material_gasto_id if booking else None),
            ).order_by('nome', 'pk')
            retained = booking.equipamentos.values_list('pk', flat=True) if booking and booking.categoria == 'servico' else []
            self.fields['equipamentos'].queryset = CATEGORY_MODELS['equipamento'].objects.filter(
                ~Q(status='indisponivel') | Q(pk__in=retained),
            ).order_by('nome', 'pk')
        else:
            for name in SERVICE_FIELDS:
                del self.fields[name]
        self.fields['versao'].required = booking is not None

    def clean_equipamentos(self):
        return [equipment.pk for equipment in self.cleaned_data['equipamentos']]

    def clean(self):
        cleaned = super().clean()
        if self.category == 'servico':
            own_material = cleaned.get('material_proprio')
            spent = cleaned.get('material_gasto_gramas')
            if own_material is False and spent is None and 'material_gasto_gramas' not in self.errors:
                self.add_error('material_gasto_gramas', 'Informe em gramas o material gasto do laboratório.')
            if own_material is False and cleaned.get('material_gasto') is None and 'material_gasto' not in self.errors:
                self.add_error('material_gasto', 'Selecione o material utilizado do laboratório.')
            if own_material is True:
                cleaned['material_gasto_gramas'] = None
                cleaned['material_gasto'] = None
        return cleaned

    def clean_material_gasto(self):
        material = self.cleaned_data['material_gasto']
        return material.pk if material else None

    def clean_objeto(self):
        resource = self.cleaned_data['objeto']
        if self.category == 'espaco' and resource.somente_administradores and not self.is_admin:
            raise forms.ValidationError('Este espaço só pode ser agendado por administradores do laboratório.')
        return resource.pk

    def clean_versao(self):
        value = self.cleaned_data.get('versao')
        if self.booking is None and value is not None:
            raise forms.ValidationError('A versão inicial é definida pelo sistema.')
        return value

    def _preserve_precision(self, name):
        value = self.cleaned_data[name]
        original = getattr(self.booking, name) if self.booking else None
        return original if original is not None and value == original.replace(microsecond=0) else value

    def clean_inicio(self):
        return self._preserve_precision('inicio')

    def clean_fim(self):
        return self._preserve_precision('fim')


class CancelForm(StrictFormMixin, forms.Form):
    versao = forms.IntegerField(min_value=1, widget=forms.HiddenInput)


class ReviewForm(StrictFormMixin, forms.Form):
    versao = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    decisao = forms.ChoiceField(choices=[('aprovar', 'Aceitar'), ('rejeitar', 'Rejeitar')])
