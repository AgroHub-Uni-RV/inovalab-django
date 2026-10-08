from django import forms
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils import timezone

from inovalab_app.agenda.models import AgendaServico
from inovalab_app.catalogo.models import Equipamento
from inovalab_app.materiais.models import Material
from inovalab_app.tarefas.models import Tarefa


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
        fields = ['agendamento_servico', 'descricao', 'responsavel', 'equipamento', 'material_gasto', 'quantidade_material_gasto']
        widgets = {
            'descricao': forms.Textarea(attrs={'rows': 4}),
        }
        help_texts = {'agendamento_servico': 'A tarefa usa o prazo do serviço vinculado. Horário de Brasília.'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['agendamento_servico'].queryset = AgendaServico.objects.filter(
            Q(situacao='confirmado', cancelado_em__isnull=True) | Q(pk=self.instance.agendamento_servico_id),
        ).select_related('servico', 'criado_por')
        self.fields['agendamento_servico'].label_from_instance = lambda booking: f'#{booking.pk} · {booking.objeto_nome}'
        self.fields['equipamento'].queryset = Equipamento.objects.filter(Q(excluido_em__isnull=True) | Q(pk=self.instance.equipamento_id))
        self.fields['material_gasto'].queryset = Material.objects.filter(Q(status='disponivel') | Q(pk=self.instance.material_gasto_id))
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

    @property
    def service_deadlines(self):
        return {str(booking.pk): timezone.localtime(booking.servico.prazo).strftime('%d/%m/%Y %H:%M')
                for booking in self.fields['agendamento_servico'].queryset}

    @property
    def selected_service_deadline(self):
        return self.service_deadlines.get(str(self['agendamento_servico'].value()), 'Selecione um agendamento de serviço.')


class StatusSelect(forms.Select):
    allowed_values = None

    def create_option(self, *args, **kwargs):
        option = super().create_option(*args, **kwargs)
        if self.allowed_values is not None and option['value'] not in self.allowed_values:
            option['attrs']['disabled'] = True
        return option


class TransitionForm(StrictFormMixin, forms.Form):
    status = forms.ChoiceField(choices=Tarefa._meta.get_field('status').choices, widget=StatusSelect)
    versao = forms.IntegerField(min_value=1, widget=forms.HiddenInput)


class DeleteForm(StrictFormMixin, forms.Form):
    versao = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
