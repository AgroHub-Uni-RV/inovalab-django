from datetime import datetime

from django import forms
from django.utils import timezone
from inovalab_app.shared.form_times import minute_value


class StrictFormMixin:
    def clean(self):
        cleaned = super().clean()
        if set(self.data) - set(self.fields) - {'csrfmiddlewaretoken'}:
            raise forms.ValidationError('Foram enviados campos que não podem ser alterados.')
        return cleaned


class BookingForm(StrictFormMixin, forms.Form):
    categoria = forms.ChoiceField(choices=[('servico', 'Serviço')], initial='servico', widget=forms.HiddenInput)
    titulo = forms.CharField(label='Título', max_length=150)
    descricao = forms.CharField(label='Descrição', widget=forms.Textarea(attrs={'rows': 4}))
    prazo_data = forms.DateField(label='Data limite', input_formats=['%Y-%m-%d'],
        widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}))
    prazo_hora = forms.TimeField(label='Hora limite', input_formats=['%H:%M', '%H:%M:%S'],
        widget=forms.TimeInput(format='%H:%M', attrs={'type': 'time', 'step': '60'}), help_text='Horário de Brasília.')
    observacoes = forms.CharField(label='Observações', required=False, widget=forms.Textarea(attrs={'rows': 3}))
    versao = forms.IntegerField(min_value=1, required=False, widget=forms.HiddenInput)

    def __init__(self, *args, booking=None, actor=None, **kwargs):
        self.booking = booking
        self.actor = actor
        self.category = 'servico'
        self.category_label = 'Serviço'
        initial = {'categoria': 'servico'}
        if booking:
            deadline = timezone.localtime(booking.servico.prazo)
            initial.update(titulo=booking.servico.titulo, descricao=booking.servico.descricao,
                prazo_data=deadline.date(), prazo_hora=deadline.time(), observacoes=booking.observacoes, versao=booking.versao)
        initial.update(kwargs.pop('initial', {}))
        super().__init__(*args, initial=initial, **kwargs)
        self.fields['versao'].required = booking is not None

    def clean_versao(self):
        value = self.cleaned_data.get('versao')
        if self.booking is None and value is not None:
            raise forms.ValidationError('A versão inicial é definida pelo sistema.')
        return value

    def clean(self):
        cleaned = super().clean()
        day, hour = cleaned.get('prazo_data'), cleaned.get('prazo_hora')
        if day and hour:
            try:
                value = forms.DateTimeField().clean(datetime.combine(day, minute_value(hour)))
            except forms.ValidationError as error:
                self.add_error('prazo_hora', error)
            else:
                cleaned['prazo'] = minute_value(value, self.booking.servico.prazo if self.booking else None)
        return cleaned


class CancelForm(StrictFormMixin, forms.Form):
    versao = forms.IntegerField(min_value=1, widget=forms.HiddenInput)


class ReviewForm(StrictFormMixin, forms.Form):
    versao = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    decisao = forms.ChoiceField(choices=[('aprovar', 'Aceitar'), ('rejeitar', 'Rejeitar')])
