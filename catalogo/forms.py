from django import forms

from catalogo.models import Equipamento, Espaco, Servico


class ServicoForm(forms.ModelForm):
    class Meta:
        model = Servico
        fields = ['nome', 'descricao', 'status']
        widgets = {'descricao': forms.Textarea(attrs={'rows': 4})}


class EquipamentoForm(forms.ModelForm):
    class Meta:
        model = Equipamento
        fields = ['nome', 'descricao', 'status']
        widgets = {'descricao': forms.Textarea(attrs={'rows': 4})}


class EspacoForm(forms.ModelForm):
    class Meta:
        model = Espaco
        fields = ['nome', 'capacidade_maxima_de_pessoas', 'status']
        widgets = {'capacidade_maxima_de_pessoas': forms.NumberInput(attrs={'min': 1, 'max': 2147483647})}
