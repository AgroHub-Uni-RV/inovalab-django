from django import forms

from conteudo.models import LocalBanner, StatusBanner
from conteudo.services import PUBLIC_FIELDS


class BannerForm(forms.Form):
    titulo = forms.CharField(label='Título', max_length=150)
    texto_alternativo = forms.CharField(label='Texto alternativo', max_length=250, required=False,
                                      help_text='Descreva a imagem. Se vazio, será usado o título.')
    banner_img = forms.FileField(label='Imagem WebP', widget=forms.FileInput,
                                help_text='WebP estático, até 5 MiB e 4096 × 4096 pixels.')
    status = forms.ChoiceField(choices=StatusBanner.choices, initial=StatusBanner.INATIVO)
    local = forms.ChoiceField(choices=LocalBanner.choices, initial=LocalBanner.HOME)
    ordem = forms.IntegerField(min_value=0, max_value=2147483647, initial=0)
    inicio_exibicao = forms.DateTimeField(label='Início (Brasília)', required=False,
        widget=forms.DateTimeInput(format='%Y-%m-%dT%H:%M:%S', attrs={'type': 'datetime-local', 'step': '1'}))
    fim_exibicao = forms.DateTimeField(label='Fim (Brasília)', required=False,
        widget=forms.DateTimeInput(format='%Y-%m-%dT%H:%M:%S', attrs={'type': 'datetime-local', 'step': '1'}))
    versao = forms.IntegerField(min_value=1, max_value=9223372036854775806, widget=forms.HiddenInput)

    def __init__(self, *args, banner=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.banner = banner
        if banner is None:
            del self.fields['versao']
        else:
            self.fields['banner_img'].required = False
            self.initial.update({key: getattr(banner, key) for key in PUBLIC_FIELDS})
            self.initial['versao'] = banner.versao

    def clean(self):
        data = super().clean()
        allowed = set(self.fields) | {'csrfmiddlewaretoken'}
        if (set(self.data) | set(self.files)) - allowed:
            raise forms.ValidationError('O formulário contém campos não permitidos.')
        if any(len(values) != 1 for source in (self.data, self.files) for _, values in source.lists()):
            raise forms.ValidationError('Envie cada campo uma única vez.')
        return data


class DeleteBannerForm(forms.Form):
    versao = forms.IntegerField(min_value=1, max_value=9223372036854775806, widget=forms.HiddenInput)

    def clean(self):
        data = super().clean()
        if set(self.data) - {'versao', 'csrfmiddlewaretoken'}:
            raise forms.ValidationError('O formulário contém campos não permitidos.')
        if any(len(values) != 1 for _, values in self.data.lists()):
            raise forms.ValidationError('Envie cada campo uma única vez.')
        return data
