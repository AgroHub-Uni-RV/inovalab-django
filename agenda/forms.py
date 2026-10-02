from django import forms
from django.db.models import Q

from agenda.models import CATEGORIES
from agenda.services import CATEGORY_MODELS


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
    versao = forms.IntegerField(min_value=1, required=False, widget=forms.HiddenInput)

    def __init__(self, *args, booking=None, **kwargs):
        self.booking = booking
        initial = {}
        if booking:
            initial.update(categoria=booking.categoria, objeto=booking.objeto_id, requerente=booking.requerente,
                           motivo=booking.motivo, inicio=booking.inicio, fim=booking.fim, versao=booking.versao)
        initial.update(kwargs.get('initial', {}))
        initial.setdefault('categoria', 'servico')
        kwargs['initial'] = initial
        super().__init__(*args, **kwargs)
        category = self.data.get('categoria') if self.is_bound else self.initial['categoria']
        if category in CATEGORY_MODELS:
            retained_id = booking.objeto_id if booking and category == booking.categoria else None
            self.fields['objeto'].queryset = CATEGORY_MODELS[category].objects.filter(
                ~Q(status='indisponivel') | Q(pk=retained_id),
            ).order_by('nome', 'pk')
        self.fields['versao'].required = booking is not None

    def clean_objeto(self):
        return self.cleaned_data['objeto'].pk

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
