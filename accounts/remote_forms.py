from django import forms
from django.contrib.auth.forms import AuthenticationForm, UsernameField

from accounts.forms import ProfileForm


class StrictRemoteForm(forms.Form):
    def clean(self):
        cleaned = super().clean()
        if set(self.data) - set(self.fields) - {'csrfmiddlewaretoken'}:
            raise forms.ValidationError('Foram enviados campos que não podem ser alterados.')
        return cleaned


class AgroHubLoginForm(AuthenticationForm):
    username = UsernameField(label='Usuário ou e-mail', widget=forms.TextInput(attrs={'autocomplete': 'username'}))


class RegisterForm(StrictRemoteForm):
    username = UsernameField(label='Usuário', max_length=150)
    email = forms.EmailField(label='E-mail')
    password = forms.CharField(label='Senha', min_length=8, max_length=128,
                               strip=False, widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}))
    password_confirm = forms.CharField(label='Confirmar senha', max_length=128, strip=False,
                                       widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}))
    first_name = forms.CharField(label='Nome', max_length=150, required=False)
    last_name = forms.CharField(label='Sobrenome', max_length=150, required=False)
    cpf = forms.CharField(label='CPF', max_length=14, required=False)
    telefone = forms.CharField(label='Telefone', max_length=20, required=False)

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('password') != cleaned.get('password_confirm'):
            self.add_error('password_confirm', 'As senhas devem ser iguais.')
        return cleaned


class AgroHubProfileForm(StrictRemoteForm):
    first_name = forms.CharField(label='Nome', max_length=150, required=False)
    last_name = forms.CharField(label='Sobrenome', max_length=150, required=False)
    cpf = forms.CharField(label='CPF', max_length=14, required=False)
    telefone = forms.CharField(label='Telefone', max_length=20, required=False)


class AgroHubPhotoForm(StrictRemoteForm):
    foto = forms.ImageField(label='Foto de perfil', required=True,
                            widget=forms.FileInput(attrs={'accept': 'image/png,image/jpeg,image/webp'}),
                            help_text='PNG, JPEG ou WebP, até 5 MB.')
    clean_foto = ProfileForm.clean_foto


class PasswordResetForm(StrictRemoteForm):
    email = forms.EmailField(label='E-mail', widget=forms.EmailInput(attrs={'autocomplete': 'email'}))


class RedactedHiddenInput(forms.HiddenInput):
    def format_value(self, value):
        return None


class PasswordResetConfirmForm(StrictRemoteForm):
    uid = forms.CharField(label='UID recebido', max_length=256, help_text='Identificador presente no link de recuperação.')
    token = forms.CharField(label='Token recebido', max_length=512,
                            widget=forms.PasswordInput(render_value=False, attrs={'autocomplete': 'off'}))
    new_password = forms.CharField(label='Nova senha', min_length=8, max_length=128, strip=False,
                                   widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}))
    new_password_confirm = forms.CharField(label='Confirmar nova senha', max_length=128, strip=False,
                                           widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}))

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('new_password') != cleaned.get('new_password_confirm'):
            self.add_error('new_password_confirm', 'As senhas devem ser iguais.')
        return cleaned
