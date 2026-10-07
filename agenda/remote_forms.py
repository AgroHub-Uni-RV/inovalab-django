from django import forms


class RemoteVisitForm(forms.Form):
    sala = forms.ChoiceField(label='Sala')
    titulo = forms.CharField(label='Título da visita', max_length=200)
    quantidade_pessoas = forms.IntegerField(label='Quantidade de pessoas', min_value=1,
                                            max_value=2147483647, initial=1)
    data = forms.DateField(label='Dia', input_formats=['%Y-%m-%d'],
                          widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}))
    hora_inicio = forms.TimeField(label='Hora de início', input_formats=['%H:%M'],
                                  widget=forms.TimeInput(format='%H:%M', attrs={'type': 'time'}))
    hora_fim = forms.TimeField(label='Hora de término', input_formats=['%H:%M'],
                               widget=forms.TimeInput(format='%H:%M', attrs={'type': 'time'}))
    observacoes = forms.CharField(label='Observações', required=False,
                                  widget=forms.Textarea(attrs={'rows': 3}))

    def __init__(self, *args, rooms=(), booking=None, **kwargs):
        from django.utils import timezone
        initial = {}
        if booking:
            start, end = timezone.localtime(booking.inicio), timezone.localtime(booking.fim)
            initial.update(titulo=booking.titulo, quantidade_pessoas=booking.quantidade_pessoas,
                           data=start.date(), hora_inicio=start.time(), hora_fim=end.time(),
                           observacoes=booking.observacoes)
        initial.update(kwargs.pop('initial', {}))
        super().__init__(*args, initial=initial, **kwargs)
        if booking:
            del self.fields['sala']
        else:
            self.fields['sala'].choices = list(rooms)

    def clean(self):
        cleaned = super().clean()
        if (set(self.data) - set(self.fields) - {'csrfmiddlewaretoken'}
                or (hasattr(self.data, 'getlist') and any(len(self.data.getlist(key)) != 1 for key in self.data))):
            raise forms.ValidationError('Confira os campos enviados; apenas os campos do formulário podem ser alterados.')
        start, end = cleaned.get('hora_inicio'), cleaned.get('hora_fim')
        if start and end and end <= start:
            self.add_error('hora_fim', 'O término deve ser posterior ao início, no mesmo dia.')
        return cleaned

    def payload(self):
        result = dict(self.cleaned_data)
        result['data'] = result['data'].isoformat()
        for name in ('hora_inicio', 'hora_fim'):
            result[name] = result[name].strftime('%H:%M')
        return result
