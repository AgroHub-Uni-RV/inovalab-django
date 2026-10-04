from queue import Queue
from threading import Barrier, Thread
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import close_old_connections, connections
from django.test import TransactionTestCase

from conteudo.models import Banner
from conteudo.services import BannerConflict, save_banner
from conteudo.tests.helpers import DATA, BannerFixtures, image_upload


class BannerConcurrencyTests(BannerFixtures, TransactionTestCase):
    def test_two_replacements_have_one_winner_and_no_losing_file(self):
        banner = save_banner(actor=self.admin, data=DATA, image=image_upload())
        old_name = banner.banner_img.name
        barrier, outcomes = Barrier(2), Queue()
        real_clean = Banner.full_clean

        def sync_clean(instance, *args, **kwargs):
            real_clean(instance, *args, **kwargs)
            barrier.wait(timeout=10)

        def replace(title, color):
            close_old_connections()
            try:
                actor = get_user_model().objects.get(pk=self.admin.pk)
                result = save_banner(actor=actor, data={'titulo': title}, banner_id=banner.pk,
                                     expected_version=1, image=image_upload(color=color))
                outcomes.put(('ok', result.titulo, result.banner_img.name))
            except BannerConflict:
                outcomes.put(('conflict',))
            except Exception as error:
                outcomes.put(('error', repr(error)))
            finally:
                connections.close_all()

        with patch.object(Banner, 'full_clean', sync_clean):
            threads = [Thread(target=replace, args=('Primeiro', 'red')), Thread(target=replace, args=('Segundo', 'green'))]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=15)
                self.assertFalse(thread.is_alive())
        results = [outcomes.get_nowait(), outcomes.get_nowait()]
        self.assertCountEqual([item[0] for item in results], ['ok', 'conflict'])
        winner = next(item for item in results if item[0] == 'ok')
        banner.refresh_from_db()
        self.assertEqual((banner.titulo, banner.banner_img.name, banner.versao), (*winner[1:], 2))
        self.assertCountEqual(self.stored_files(), [old_name, banner.banner_img.name])
