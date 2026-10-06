from io import BytesIO

from PIL import Image, ImageOps
from django import forms
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import UploadedFile

from accounts.models import User


class ProfileForm(forms.ModelForm):
    foto = forms.ImageField(label='Foto de perfil', required=False,
                           widget=forms.FileInput(attrs={'accept':'image/png,image/jpeg,image/webp'}),
                           help_text='PNG, JPEG ou WebP, até 5 MB.')

    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'foto')
        labels = {'username':'Nome de usuário (login)', 'first_name':'Nome', 'last_name':'Sobrenome'}
        widgets = {'username':forms.TextInput(attrs={'autocomplete':'username'}),
                   'first_name':forms.TextInput(attrs={'autocomplete':'given-name'}),
                   'last_name':forms.TextInput(attrs={'autocomplete':'family-name'})}

    def clean_foto(self):
        photo = self.cleaned_data['foto']
        if not isinstance(photo, UploadedFile):
            return photo
        if photo.size > 5 * 1024 * 1024:
            raise forms.ValidationError('A foto deve ter até 5 MB.')
        try:
            photo.seek(0)
            with Image.open(photo) as image:
                if image.format not in ('PNG', 'JPEG', 'WEBP'):
                    raise forms.ValidationError('Use uma imagem PNG, JPEG ou WebP.')
                if image.width * image.height > 16_000_000:
                    raise forms.ValidationError('A imagem deve ter até 16 milhões de pixels.')
                image = ImageOps.exif_transpose(image).convert('RGBA')
                image.thumbnail((512, 512))
                output = BytesIO()
                image.save(output, format='WEBP', quality=85)
        except (OSError, ValueError, Image.DecompressionBombError) as error:
            raise forms.ValidationError('Não foi possível ler a imagem.') from error
        return ContentFile(output.getvalue(), name='foto.webp')
