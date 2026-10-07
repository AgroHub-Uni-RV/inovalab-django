from django import forms


class ContactForm(forms.Form):
    nome = forms.CharField(label='Nome completo', min_length=2, max_length=120,
                          widget=forms.TextInput(attrs={'autocomplete': 'name', 'placeholder': 'Seu nome completo'}))
    telefone = forms.CharField(label='Telefone', max_length=20, required=False,
                              widget=forms.TextInput(attrs={'autocomplete': 'tel', 'inputmode': 'tel',
                                                            'placeholder': '(DDD) 9 8765-4321'}))
    email = forms.EmailField(label='E-mail', max_length=254,
                            widget=forms.EmailInput(attrs={'autocomplete': 'email', 'placeholder': 'Seu e-mail'}))
    mensagem = forms.CharField(label='Mensagem', min_length=10, max_length=10000,
                               widget=forms.Textarea(attrs={'rows': 6, 'placeholder': 'Como podemos ajudar?'}))
    consent = forms.BooleanField(label='Concordo com os termos e a política de privacidade.',
                                 error_messages={'required': 'Confirme a leitura dos termos e da política de privacidade.'})
    website = forms.CharField(required=False, widget=forms.HiddenInput(attrs={'autocomplete': 'off'}))

    def clean_nome(self):
        value = ' '.join(self.cleaned_data['nome'].split())
        if len(value) < 2:
            raise forms.ValidationError('Informe seu nome completo.')
        return value

    def clean_email(self):
        return self.cleaned_data['email'].strip().lower()

    def clean_website(self):
        if self.cleaned_data.get('website'):
            raise forms.ValidationError('Não foi possível enviar este formulário.')
        return ''
