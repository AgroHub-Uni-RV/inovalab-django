from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings


DATA = {'titulo': 'Banner laboratório', 'local': 'home', 'status': 'ativo', 'ordem': 0,
        'texto_alternativo': 'Laboratório'}


def image_upload(format='WEBP', name='banner.webp', size=(32, 16), color='blue'):
    buffer = BytesIO()
    Image.new('RGB', size, color).save(buffer, format=format)
    return SimpleUploadedFile(name, buffer.getvalue(), content_type='image/webp')


class BannerFixtures:
    def setUp(self):
        super().setUp()
        self.media = TemporaryDirectory()
        self.addCleanup(self.media.cleanup)
        self.settings_override = override_settings(MEDIA_ROOT=self.media.name)
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.admin = get_user_model().objects.create_user('gestor-banner', is_superuser=True)
        self.user = get_user_model().objects.create_user('leitor-banner', is_staff=True)

    def stored_files(self):
        return sorted(path.relative_to(self.media.name).as_posix() for path in Path(self.media.name).rglob('*') if path.is_file())
