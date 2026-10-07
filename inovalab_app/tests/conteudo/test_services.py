from datetime import datetime, timedelta, timezone as dt_timezone
from io import BytesIO
from unittest.mock import patch

from PIL import Image
from django.contrib.auth.models import AnonymousUser, Group
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from inovalab_app.conteudo.models import Banner
from inovalab_app.conteudo.selectors import published_banners, visible_banners
from inovalab_app.conteudo.services import BannerConflict, delete_banner, save_banner
from inovalab_app.tests.conteudo.helpers import DATA, BannerFixtures, image_upload


class BannerServiceTests(BannerFixtures, TestCase):
    def create(self, **changes):
        return save_banner(actor=self.admin, data={**DATA, **changes}, image=image_upload())

    def test_normalized_create_stores_webp_with_generated_name(self):
        banner = self.create(titulo=' Título ', texto_alternativo=' Alternativa ')
        self.assertEqual((banner.titulo, banner.texto_alternativo, banner.versao), ('Título', 'Alternativa', 1))
        self.assertTrue(banner.banner_img.name.startswith('banners/'))
        self.assertNotEqual(banner.banner_img.name, 'banners/banner.webp')
        with banner.banner_img.open('rb') as handle:
            self.assertEqual(Image.open(handle).format, 'WEBP')

    def test_only_active_business_admins_manage_and_consult_full_records(self):
        banner = self.create(status='inativo')
        self.admin.is_active = False
        for actor in (self.admin, self.user, AnonymousUser()):
            with self.subTest(actor=actor):
                with self.assertRaises(PermissionDenied):
                    save_banner(actor=actor, data=DATA, image=image_upload())
                self.assertFalse(visible_banners(actor).exists())
        self.user.groups.add(Group.objects.get(name='Administradores'))
        self.assertEqual(list(visible_banners(self.user)), [banner])
        self.assertEqual(save_banner(actor=self.user, data=DATA, image=image_upload()).status, 'ativo')

    def test_invalid_fields_and_missing_image_never_write(self):
        for changes in ({'titulo': ' '}, {'titulo': 'x'*151}, {'local': 'admin'}, {'status': 'rascunho'},
                        {'ordem': -1}, {'ordem': True}, {'ordem': 1.5}, {'ordem': 2147483648}, {'versao': 4}):
            with self.subTest(changes=changes):
                with self.assertRaises(ValidationError):
                    self.create(**changes)
        with self.assertRaises(ValidationError):
            save_banner(actor=self.admin, data=DATA)
        self.assertEqual(Banner.objects.count(), 0)
        self.assertEqual(self.stored_files(), [])

    def test_fake_corrupt_and_oversized_webp_rejected_before_storage(self):
        webp = image_upload().read()
        invalid = [image_upload(format='PNG'), SimpleUploadedFile('fake.webp', b'not an image'),
                   SimpleUploadedFile('truncated.webp', webp[:20]),
                   SimpleUploadedFile('large.webp', webp + b'x' * (5 * 1024 * 1024)),
                   image_upload(size=(4097, 1))]
        for upload in invalid:
            with self.subTest(name=upload.name):
                with self.assertRaises(ValidationError):
                    save_banner(actor=self.admin, data=DATA, image=upload)
        self.assertEqual(self.stored_files(), [])

    def test_animated_webp_is_rejected(self):
        buffer = BytesIO()
        Image.new('RGB', (16, 16), 'blue').save(buffer, format='WEBP', save_all=True,
            append_images=[Image.new('RGB', (16, 16), 'red')], duration=100, loop=0)
        with self.assertRaises(ValidationError):
            save_banner(actor=self.admin, data=DATA,
                        image=SimpleUploadedFile('animated.webp', buffer.getvalue()))

    def test_uploaded_filename_and_mimetype_do_not_determine_format(self):
        banner = save_banner(actor=self.admin, data=DATA, image=image_upload(name='untrusted.png'))
        self.assertTrue(banner.banner_img.name.endswith('.webp'))

    def test_scheduled_period_requires_aware_complete_ordered_dates(self):
        start = datetime.fromisoformat('2026-11-01T10:00:00-03:00')
        for period in ({}, {'inicio_exibicao': start},
                       {'inicio_exibicao': start, 'fim_exibicao': start},
                       {'inicio_exibicao': start.replace(tzinfo=None), 'fim_exibicao': start + timedelta(hours=1)}):
            with self.subTest(period=period):
                with self.assertRaises(ValidationError):
                    self.create(status='agendado', **period)
        with self.assertRaises(ValidationError):
            self.create(inicio_exibicao=start, fim_exibicao=start + timedelta(hours=1))

    def test_publication_has_exact_boundaries_and_local_order(self):
        start = datetime.fromisoformat('2026-11-01T10:00:00-03:00')
        first = self.create(ordem=1)
        scheduled = self.create(status='agendado', ordem=0, inicio_exibicao=start,
                                fim_exibicao=start + timedelta(hours=1))
        second = self.create(ordem=1)
        self.create(status='inativo')
        self.create(local='sobre')
        self.assertEqual(list(published_banners('home', at=start-timedelta(microseconds=1))), [first, second])
        self.assertEqual(list(published_banners('home', at=start)), [scheduled, first, second])
        self.assertEqual(list(published_banners('home', at=start+timedelta(hours=1))), [first, second])
        scheduled.refresh_from_db()
        self.assertEqual(scheduled.inicio_exibicao, datetime(2026, 11, 1, 13, tzinfo=dt_timezone.utc))

    def test_edit_and_replacement_preserve_old_file_and_stable_id(self):
        banner = self.create()
        old_file = banner.banner_img.name
        updated = save_banner(actor=self.admin, banner_id=banner.pk, expected_version=1,
                              data={'titulo': 'Corrigido', 'local': 'sobre'}, image=image_upload(color='red'))
        self.assertEqual((updated.pk, updated.versao, updated.local), (banner.pk, 2, 'sobre'))
        self.assertNotEqual(old_file, updated.banner_img.name)
        self.assertEqual(len(self.stored_files()), 2)
        self.assertTrue(updated.banner_img.storage.exists(old_file))

    def test_stale_and_invalid_update_preserve_record_and_files(self):
        banner = self.create()
        save_banner(actor=self.admin, banner_id=banner.pk, expected_version=1, data={'titulo': 'Vencedor'})
        for version in (None, True, '2', 0):
            with self.assertRaises(ValidationError):
                save_banner(actor=self.admin, banner_id=banner.pk, expected_version=version, data={})
        with self.assertRaises(BannerConflict):
            save_banner(actor=self.admin, banner_id=banner.pk, expected_version=1,
                        data={'titulo': 'Perdedor'}, image=image_upload())
        with self.assertRaises(ValidationError):
            save_banner(actor=self.admin, banner_id=banner.pk, expected_version=2,
                        data={'local': 'inválido'}, image=image_upload())
        banner.refresh_from_db()
        self.assertEqual((banner.titulo, banner.versao), ('Vencedor', 2))
        self.assertEqual(len(self.stored_files()), 1)

    def test_database_failure_cleans_only_new_upload(self):
        existing = self.create()
        with patch.object(Banner, 'save', side_effect=RuntimeError('falha de gravação')):
            with self.assertRaises(RuntimeError):
                self.create()
        self.assertEqual(self.stored_files(), [existing.banner_img.name])
        self.assertEqual(Banner.objects.count(), 1)

    def test_logical_deletion_requires_version_and_preserves_image(self):
        banner = self.create()
        with self.assertRaises(PermissionDenied):
            delete_banner(actor=self.user, banner_id=banner.pk, expected_version=1)
        with self.assertRaises(BannerConflict):
            delete_banner(actor=self.admin, banner_id=banner.pk, expected_version=2)
        delete_banner(actor=self.admin, banner_id=banner.pk, expected_version=1)
        banner.refresh_from_db()
        self.assertIsNotNone(banner.excluido_em)
        self.assertEqual(banner.versao, 2)
        self.assertFalse(published_banners('home').exists())
        self.assertFalse(visible_banners(self.admin).exists())
        self.assertTrue(banner.banner_img.storage.exists(banner.banner_img.name))
