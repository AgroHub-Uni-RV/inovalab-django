from django import forms

from agenda.forms import StrictFormMixin
from agenda.models import AgendaVisita


class VisitForm(StrictFormMixin, forms.ModelForm):
    categoria = forms.ChoiceField(choices=[('visita', 'Visita')], required=False, initial='visita', widget=forms.HiddenInput)
    versao = forms.IntegerField(min_value=1, required=False, widget=forms.HiddenInput)

    class Meta:
        model = AgendaVisita
        fields = ['quantidade_pessoas', 'data', 'hora_inicio', 'hora_termino', 'observacoes']
        labels = {'quantidade_pessoas': 'Quantidade de pessoas', 'data': 'Data',
                  'hora_inicio': 'Hora de início', 'hora_termino': 'Hora de término'}
        widgets = {
            'data': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
            'hora_inicio': forms.TimeInput(format='%H:%M:%S', attrs={'type': 'time', 'step': '1'}),
            'hora_termino': forms.TimeInput(format='%H:%M:%S', attrs={'type': 'time', 'step': '1'}),
            'observacoes': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, booking=None, **kwargs):
        self.booking = booking
        if booking:
            kwargs['instance'] = booking
            kwargs['initial'] = {'versao': booking.versao}
        super().__init__(*args, **kwargs)
        self.fields['versao'].required = booking is not None
        self.fields['hora_inicio'].help_text = 'Horário de Brasília.'

    def clean_versao(self):
        version = self.cleaned_data.get('versao')
        if self.booking is None and version is not None:
            raise forms.ValidationError('A versão inicial é definida pelo sistema.')
        return version
