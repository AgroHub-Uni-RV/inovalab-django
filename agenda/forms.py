from decimal import Decimal
from datetime import datetime

from django import forms
from django.db.models import Q
from django.utils import timezone
from accounts.policies import is_business_admin

from agenda.models import CATEGORIES
from agenda.services import CATEGORY_MODELS, SERVICE_FIELDS
from agenda.widgets import EquipmentCheckboxSelectMultiple, EquipmentRadioSelect
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
    motivo = forms.CharField(label='Motivo', widget=forms.Textarea(attrs={'rows': 3}))
    observacoes = forms.CharField(label='Observações', required=False, help_text='Opcional.',
                                  widget=forms.Textarea(attrs={'rows': 3}))
    dia = forms.DateField(label='Dia', input_formats=['%Y-%m-%d'],
                          widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}))
    hora_inicio = forms.TimeField(label='Hora de início', help_text='Horário de Brasília.',
                                 input_formats=['%H:%M', '%H:%M:%S'],
                                 widget=forms.TimeInput(format='%H:%M:%S', attrs={'type': 'time', 'step': '1'}))
    hora_termino = forms.TimeField(label='Hora de término', input_formats=['%H:%M', '%H:%M:%S'],
                                  widget=forms.TimeInput(format='%H:%M:%S', attrs={'type': 'time', 'step': '1'}))
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
        self.legacy_multiday = False
        if booking:
            start, end = timezone.localtime(booking.inicio), timezone.localtime(booking.fim)
            self.legacy_multiday = start.date() != end.date()
            initial.update(categoria=booking.categoria, objeto=booking.objeto_id, motivo=booking.motivo,
                           observacoes=booking.observacoes,
                           dia=start.date(), hora_inicio=start.time().replace(microsecond=0),
                           hora_termino=end.time().replace(microsecond=0), versao=booking.versao)
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
            if category == 'equipamento':
                self.fields['objeto'].empty_label = None
                self.fields['objeto'].widget = EquipmentRadioSelect(choices=self.fields['objeto'].choices)
        if category == 'visita':
            for name in ('objeto', 'motivo', 'observacoes'):
                del self.fields[name]
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
        self._clean_period(cleaned)
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
        return resource.pk

    def clean_versao(self):
        value = self.cleaned_data.get('versao')
        if self.booking is None and value is not None:
            raise forms.ValidationError('A versão inicial é definida pelo sistema.')
        return value

    def _preserve_precision(self, name, value):
        original = getattr(self.booking, name) if self.booking else None
        return original if original is not None and value == original.replace(microsecond=0) else value

    def _clean_period(self, cleaned):
        day, start, end = (cleaned.get(name) for name in ('dia', 'hora_inicio', 'hora_termino'))
        if day is None or start is None or end is None:
            return
        if self.booking:
            original_start, original_end = timezone.localtime(self.booking.inicio), timezone.localtime(self.booking.fim)
            if (day, start, end) == (original_start.date(), original_start.time().replace(microsecond=0),
                                      original_end.time().replace(microsecond=0)):
                cleaned.update(inicio=self.booking.inicio, fim=self.booking.fim)
                return
        if end <= start:
            self.add_error('hora_termino', 'O término deve ser posterior ao início, no mesmo dia.')
            return
        for name, hour, field in [('inicio', start, 'hora_inicio'), ('fim', end, 'hora_termino')]:
            try:
                value = forms.DateTimeField().clean(datetime.combine(day, hour))
            except forms.ValidationError as error:
                self.add_error(field, error)
            else:
                cleaned[name] = self._preserve_precision(name, value)


class CancelForm(StrictFormMixin, forms.Form):
    versao = forms.IntegerField(min_value=1, widget=forms.HiddenInput)


class ReviewForm(StrictFormMixin, forms.Form):
    versao = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    decisao = forms.ChoiceField(choices=[('aprovar', 'Aceitar'), ('rejeitar', 'Rejeitar')])
