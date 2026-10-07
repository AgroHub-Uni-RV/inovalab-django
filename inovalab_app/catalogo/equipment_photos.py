from pathlib import Path
from urllib.parse import urlencode

from django.core.files import File
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
        initial = self._initial_path(name)
        if initial:
            if mode not in ('r', 'rb'):
                raise PermissionError('As fotos de referência são somente leitura.')
            return File(initial.open(mode), name=name)
        return super()._open(name, mode)

    def exists(self, name):
        initial = self._initial_path(name)
        return initial.is_file() if initial else super().exists(name)

    def path(self, name):
        initial = self._initial_path(name)
        return str(initial) if initial else super().path(name)

    def delete(self, name):
        if not self._initial_path(name):
            super().delete(name)

    def url(self, name):
        return reverse('catalogo:equipment-photo') + '?' + urlencode({'arquivo': name})
