from django import forms

from inovalab_app.catalogo.models import Equipamento, Servico


class ServicoForm(forms.ModelForm):
    class Meta:
        model = Servico
        fields = ['titulo', 'descricao', 'prazo']
        widgets = {'descricao': forms.Textarea(attrs={'rows': 4})}


class EquipamentoForm(forms.ModelForm):
    class Meta:
        model = Equipamento
        fields = ['nome', 'descricao', 'foto', 'status']
        widgets = {'descricao': forms.Textarea(attrs={'rows': 4})}
