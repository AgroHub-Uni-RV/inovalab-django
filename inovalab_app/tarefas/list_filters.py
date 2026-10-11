from django import forms
from django.contrib.auth import get_user_model

from inovalab_app.tarefas.models import StatusTarefa
from inovalab_app.tarefas.selectors import visible_tasks


class TaskListFilters(forms.Form):
    responsavel = forms.ModelChoiceField(label='Responsável', required=False,
        queryset=get_user_model().objects.none(), empty_label='Todos os responsáveis')
    de = forms.DateField(label='De', required=False, widget=forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'))
    ate = forms.DateField(label='Até', required=False, widget=forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'))

    def __init__(self, data=None, *, actor):
        super().__init__(data)
        self.fields['responsavel'].queryset = get_user_model().objects.filter(
            pk__in=visible_tasks(actor).values('responsaveis__pk')).order_by('first_name', 'username')

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('de') and cleaned.get('ate') and cleaned['de'] > cleaned['ate']:
            self.add_error('ate', 'A data final deve ser igual ou posterior à inicial.')
        return cleaned
