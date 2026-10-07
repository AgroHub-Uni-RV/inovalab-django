from django import forms

from agenda.forms import StrictFormMixin
from agenda.models import AgendaVisita
from core.form_times import minute_value


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
            'hora_inicio': forms.TimeInput(format='%H:%M', attrs={'type': 'time', 'step': '60'}),
            'hora_termino': forms.TimeInput(format='%H:%M', attrs={'type': 'time', 'step': '60'}),
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

    def _clean_time(self, name):
        original = (getattr(self.booking, name) if self.booking and
                    self.cleaned_data.get('data') == self.booking.data else None)
        return minute_value(self.cleaned_data.get(name), original)

    def clean_hora_inicio(self):
        return self._clean_time('hora_inicio')

    def clean_hora_termino(self):
        return self._clean_time('hora_termino')
