from django import forms
import re
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils import timezone

from inovalab_app.agenda.models import AgendaServico
from inovalab_app.catalogo.models import Equipamento
from inovalab_app.tarefas.models import Tarefa
from inovalab_app.tarefas.material_forms import TaskMaterialFormSet


class StrictFormMixin:
    def clean(self):
        cleaned = super().clean()
        unknown = set(self.data) - set(self.fields) - {'csrfmiddlewaretoken'} - getattr(self, 'allowed_extra_keys', set())
        if unknown:
            raise forms.ValidationError('Foram enviados campos que não podem ser alterados.')
        return cleaned


class TaskForm(StrictFormMixin, forms.ModelForm):
    versao = forms.IntegerField(min_value=1, required=False, widget=forms.HiddenInput)

    class Meta:
        model = Tarefa
        fields = ['agendamento_servico', 'descricao', 'responsaveis', 'equipamentos']
        widgets = {
            'descricao': forms.Textarea(attrs={'rows': 4}),
            'responsaveis': forms.CheckboxSelectMultiple,
            'equipamentos': forms.CheckboxSelectMultiple,
        }
        help_texts = {
            'agendamento_servico': 'A tarefa usa o prazo do serviço vinculado. Horário de Brasília.',
            'responsaveis': 'Selecione pelo menos uma pessoa. Todos os responsáveis acessam e executam a mesma tarefa.',
            'equipamentos': 'Opcional. Marque todos os equipamentos necessários para a execução.',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['agendamento_servico'].queryset = AgendaServico.objects.filter(
            Q(situacao='confirmado', cancelado_em__isnull=True) | Q(pk=self.instance.agendamento_servico_id),
        ).select_related('servico', 'criado_por')
        self.fields['agendamento_servico'].label_from_instance = lambda booking: f'#{booking.pk} · {booking.objeto_nome}'
        existing_equipment = self.instance.equipamentos.values_list('pk', flat=True) if self.instance.pk else []
        existing_users = self.instance.responsaveis.values_list('pk', flat=True) if self.instance.pk else []
        self.fields['equipamentos'].queryset = Equipamento.objects.filter(Q(excluido_em__isnull=True) | Q(pk__in=existing_equipment))
        self.fields['responsaveis'].queryset = get_user_model().objects.filter(
            Q(is_active=True) | Q(pk__in=existing_users),
        ).order_by('username', 'pk')
        initial = [{'material': entry.material_id, 'quantidade': entry.quantidade}
                   for entry in self.instance.materiais_gastos.all()] if self.instance.pk else []
        self.material_formset = TaskMaterialFormSet(self.data if self.is_bound else None, prefix='materiais',
                                                   initial=initial, task=self.instance)
        self.allowed_extra_keys = {'adicionar_material'} | {
            key for key in self.data if re.fullmatch(r'materiais-(TOTAL_FORMS|INITIAL_FORMS|MIN_NUM_FORMS|MAX_NUM_FORMS|\d+-(material|quantidade|DELETE))', key)
        }
        if self.instance.pk:
            self.fields['versao'].required = True
            self.fields['versao'].initial = self.instance.versao

    def clean(self):
        cleaned = super().clean()
        if not self.material_formset.is_valid():
            raise forms.ValidationError('Confira os materiais e suas quantidades.')
        cleaned['materiais_gastos'] = self.material_formset.task_materials()
        return cleaned

    def clean_versao(self):
        version = self.cleaned_data.get('versao')
        if not self.instance.pk and version is not None:
            raise forms.ValidationError('A versão inicial é definida pelo sistema.')
        return version

    def clean_responsaveis(self):
        return list(self.cleaned_data['responsaveis'])

    def clean_equipamentos(self):
        return list(self.cleaned_data['equipamentos'])

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
