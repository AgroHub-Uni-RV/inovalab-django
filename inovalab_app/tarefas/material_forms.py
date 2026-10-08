from django import forms
from django.db.models import Q

from inovalab_app.materiais.models import Material


class TaskMaterialForm(forms.Form):
    material = forms.ModelChoiceField(queryset=Material.objects.none(), required=False)
    quantidade = forms.CharField(label='Quantidade gasta', max_length=150, required=False)

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('quantidade') and not cleaned.get('material') and not cleaned.get('DELETE'):
            self.add_error('material', 'Selecione o material da quantidade informada.')
        return cleaned


class BaseTaskMaterialFormSet(forms.BaseFormSet):
    def __init__(self, *args, task=None, **kwargs):
        super().__init__(*args, **kwargs)
        existing = task.materiais_gastos.values_list('material_id', flat=True) if task and task.pk else []
        self.material_queryset = Material.objects.filter(Q(status='disponivel') | Q(pk__in=existing)).order_by('nome', 'pk')

    def _construct_form(self, index, **kwargs):
        form = super()._construct_form(index, **kwargs)
        form.fields['material'].queryset = self.material_queryset
        return form

    @property
    def empty_form(self):
        form = super().empty_form
        form.fields['material'].queryset = self.material_queryset
        return form

    def clean(self):
        super().clean()
        if any(self.errors):
            return
        seen = set()
        for form in self.forms:
            if form.cleaned_data.get('DELETE'):
                continue
            material = form.cleaned_data.get('material')
            if material is None:
                continue
            if material.pk in seen:
                raise forms.ValidationError('Selecione cada material apenas uma vez.')
            seen.add(material.pk)

    def task_materials(self):
        return [{'material': form.cleaned_data['material'], 'quantidade': form.cleaned_data.get('quantidade', '')}
                for form in self.forms if form.cleaned_data.get('material') and not form.cleaned_data.get('DELETE')]


TaskMaterialFormSet = forms.formset_factory(TaskMaterialForm, formset=BaseTaskMaterialFormSet,
                                          extra=1, can_delete=True)
