from tempfile import TemporaryDirectory
from django.test import override_settings

class PrivateArchiveMixin:
    def setUp(self):
        super().setUp()
        temporary = TemporaryDirectory(prefix='agenda-migration-')
        self.addCleanup(temporary.cleanup)
        settings = override_settings(AGENDAS_LEGACY_ARCHIVE_DIR=temporary.name)
        settings.enable()
        self.addCleanup(settings.disable)
        self.archive_directory = temporary.name
