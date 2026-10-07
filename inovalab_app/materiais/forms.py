from decimal import Decimal

from django import forms

from inovalab_app.materiais.models import Material
from inovalab_app.materiais.services import PUBLIC_FIELDS


class MaterialCreateForm(forms.ModelForm):
    quantidade = forms.DecimalField(label='Quantidade', max_digits=12, decimal_places=3,
                                    min_value=Decimal('0'), max_value=Decimal('999999999.999'), localize=True,
                                    widget=forms.TextInput(attrs={'inputmode': 'decimal'}))

    def clean(self):
        cleaned = super().clean()
        if set(self.data) - set(self.fields) - {'csrfmiddlewaretoken'}:
            raise forms.ValidationError('Foram enviados campos que não podem ser alterados.')
        return cleaned

    class Meta:
        model = Material
        fields = PUBLIC_FIELDS
        help_texts = {'categoria': 'Categoria livre do material.', 'unidade': 'Ex.: kg, g, m ou unidade.',
                      'fonte': 'Descrição livre da origem do material.'}


class MaterialUpdateForm(MaterialCreateForm):
    versao = forms.IntegerField(min_value=1, max_value=9223372036854775806, widget=forms.HiddenInput)
