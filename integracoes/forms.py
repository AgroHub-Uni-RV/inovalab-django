from django import forms


class StrictFormMixin:
    def clean(self):
        cleaned = super().clean()
        if set(self.data) - set(self.fields) - {'csrfmiddlewaretoken'}:
            raise forms.ValidationError('Foram enviados campos que não podem ser alterados.')
        return cleaned


class ClientCreateForm(StrictFormMixin, forms.Form):
    nome = forms.CharField(label='Nome do sistema', max_length=100)


class ClientUpdateForm(ClientCreateForm):
    ativo = forms.BooleanField(label='Integrador ativo', required=False,
                              help_text='Desativar revoga a credencial. Reativar exige gerar uma nova.')
    versao = forms.IntegerField(min_value=1, max_value=9223372036854775807, widget=forms.HiddenInput)


class CredentialForm(StrictFormMixin, forms.Form):
    versao = forms.IntegerField(min_value=1, max_value=9223372036854775807, widget=forms.HiddenInput)
