from django import forms
from django.contrib.auth import get_user_model
from django.db.models import Q

from catalogo.models import Servico
from tarefas.models import Tarefa


ACTION_LABELS = {
    'iniciar': 'Iniciar execução', 'enviar': 'Enviar para avaliação',
    'aprovar': 'Aprovar entrega', 'recusar': 'Devolver para criação', 'reabrir': 'Reabrir tarefa',
}


class StrictFormMixin:
    def clean(self):
        cleaned = super().clean()
        unknown = set(self.data) - set(self.fields) - {'csrfmiddlewaretoken'}
        if unknown:
            raise forms.ValidationError('Foram enviados campos que não podem ser alterados.')
        return cleaned


class TaskForm(StrictFormMixin, forms.ModelForm):
    versao = forms.IntegerField(min_value=1, required=False, widget=forms.HiddenInput)

    class Meta:
        model = Tarefa
        fields = ['servico', 'descricao', 'responsavel', 'prazo']
        widgets = {
            'descricao': forms.Textarea(attrs={'rows': 4}),
            'prazo': forms.DateTimeInput(format='%Y-%m-%dT%H:%M:%S', attrs={'type': 'datetime-local', 'step': '1'}),
        }
        help_texts = {'prazo': 'Opcional. Horário de Brasília; tarefas vencidas continuam executáveis.'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['servico'].queryset = Servico.objects.filter(Q(status='disponivel') | Q(pk=self.instance.servico_id))
        self.fields['responsavel'].queryset = get_user_model().objects.filter(
            Q(is_active=True) | Q(pk=self.instance.responsavel_id),
        ).order_by('username', 'pk')
        if self.instance.pk:
            self.fields['versao'].required = True
            self.fields['versao'].initial = self.instance.versao

    def clean_versao(self):
        version = self.cleaned_data.get('versao')
        if not self.instance.pk and version is not None:
            raise forms.ValidationError('A versão inicial é definida pelo sistema.')
        return version

    def clean_prazo(self):
        value = self.cleaned_data.get('prazo')
        original = self.instance.prazo
        # The browser edits seconds; preserve finer API precision when this field is unchanged.
        if original is not None and value == original.replace(microsecond=0):
            return original
        return value


class TransitionForm(StrictFormMixin, forms.Form):
    acao = forms.ChoiceField(choices=ACTION_LABELS.items())
    versao = forms.IntegerField(min_value=1, widget=forms.HiddenInput)


class DeleteForm(StrictFormMixin, forms.Form):
    versao = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
