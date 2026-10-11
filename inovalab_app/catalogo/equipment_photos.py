from pathlib import Path
from io import BytesIO
from urllib.parse import urlencode

from django.core.files import File
from django.core.exceptions import ValidationError
from django.core.files.storage import FileSystemStorage
from django.urls import reverse
from django.utils.deconstruct import deconstructible


INITIAL_EQUIPMENT_PHOTOS = {
    'plotter-impressao': 'plotter-impressao.webp',
    'impressora-3d': 'impressora-3d.webp',
    'corte-laser': 'corte-laser.webp',
    'plotter-corte': 'plotter-corte.webp',
    'realidade-virtual': 'realidade-virtual.webp',
    'scanner-3d': 'scanner-3d.webp',
}
INITIAL_PHOTO_NAMES = {'iniciais/' + filename: filename for filename in INITIAL_EQUIPMENT_PHOTOS.values()}
# Historical migration names remain readable when migrating backwards.
INITIAL_PHOTO_NAMES.update({
    'iniciais/' + Path(filename).with_suffix(extension).name: filename
    for filename in INITIAL_EQUIPMENT_PHOTOS.values()
    for extension in ('.png', '.jpg')
})


@deconstructible
class EquipmentPhotoStorage(FileSystemStorage):
    """Uploaded photos use media; bundled references work on every fresh checkout."""

    def _initial_path(self, name):
        filename = INITIAL_PHOTO_NAMES.get(name)
        return Path(__file__).parent.parent / 'static' / 'inovalab_app' / 'catalogo' / 'equipamentos' / filename if filename else None

    def _open(self, name, mode='rb'):
        if name.startswith('banco/'):
            from inovalab_app.catalogo.models import Equipamento
            content = Equipamento.objects.filter(foto=name).values_list('foto_webp', flat=True).first()
            if not content or mode not in ('r', 'rb'):
                raise FileNotFoundError(name)
            return File(BytesIO(bytes(content)), name=name)
        initial = self._initial_path(name)
        if initial:
            if mode not in ('r', 'rb'):
                raise PermissionError('As fotos de referência são somente leitura.')
            return File(initial.open(mode), name=name)
        return super()._open(name, mode)

    def exists(self, name):
        if name.startswith('banco/'):
            from inovalab_app.catalogo.models import Equipamento
            return Equipamento.objects.filter(foto=name).exclude(foto_webp=b'').exists()
        initial = self._initial_path(name)
        return initial.is_file() if initial else super().exists(name)

    def path(self, name):
        initial = self._initial_path(name)
        return str(initial) if initial else super().path(name)

    def delete(self, name):
        if not name.startswith('banco/') and not self._initial_path(name):
            super().delete(name)

    def url(self, name):
        return reverse('catalogo:equipment-photo') + '?' + urlencode({'arquivo': name})


def to_webp(upload):
    """Decode once at write time; serve the stored WebP without conversions."""
    from PIL import Image, ImageOps, UnidentifiedImageError
    try:
        upload.seek(0)
        with Image.open(upload) as image:
            image = ImageOps.exif_transpose(image)
            image.thumbnail((1920, 1920))
            converted = image.convert('RGBA' if image.mode in ('RGBA', 'LA', 'P') else 'RGB')
            output = BytesIO()
            converted.save(output, format='WEBP', quality=85, method=6)
            return output.getvalue()
    except (OSError, ValueError, UnidentifiedImageError, Image.DecompressionBombError) as error:
        raise ValidationError({'foto': 'Envie uma imagem válida para a foto do equipamento.'}) from error
