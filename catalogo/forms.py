from django import forms

from catalogo.models import Equipamento, Servico


class ServicoForm(forms.ModelForm):
    class Meta:
        model = Servico
        fields = ['nome', 'descricao', 'status']
        widgets = {'descricao': forms.Textarea(attrs={'rows': 4})}


class EquipamentoForm(forms.ModelForm):
    class Meta:
        model = Equipamento
        fields = ['nome', 'descricao', 'foto', 'status']
        widgets = {'descricao': forms.Textarea(attrs={'rows': 4})}
