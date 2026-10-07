from decimal import Decimal
from queue import Queue
from threading import Barrier, Thread
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import close_old_connections, connections
from django.test import TransactionTestCase

from inovalab_app.materiais.models import Material
from inovalab_app.materiais.services import MaterialConflict, save_material
from inovalab_app.tests.materiais.test_services import DATA


class MaterialConcurrencyTests(TransactionTestCase):
    def test_concurrent_corrections_have_only_one_winner(self):
        admin = get_user_model().objects.create_user('gestor-concorrencia')
        admin.groups.add(Group.objects.get_or_create(name='Administradores')[0])
        material = save_material(actor=admin, data=DATA)
        barrier = Barrier(2)
        outcomes = Queue()
        real_clean = Material.full_clean

        def synchronized_clean(instance, *args, **kwargs):
            # Force both real connections to validate version 1 before either UPDATE.
            real_clean(instance, *args, **kwargs)
            barrier.wait(timeout=10)

        def correct(name, quantity, unit):
            close_old_connections()
            try:
                actor = get_user_model().objects.get(pk=admin.pk)
                result = save_material(actor=actor, material_id=material.pk, expected_version=1,
                                       data={'nome': name, 'quantidade': quantity, 'unidade': unit})
                outcomes.put(('ok', result.nome, result.quantidade, result.unidade))
            except MaterialConflict:
                outcomes.put(('conflict',))
            except Exception as error:
                outcomes.put(('error', repr(error)))
            finally:
                connections.close_all()

        with patch.object(Material, 'full_clean', synchronized_clean):
            workers = [Thread(target=correct, args=('Primeiro', '8', 'g')),
                       Thread(target=correct, args=('Segundo', '6', 'kg'))]
            for worker in workers:
                worker.start()
            for worker in workers:
                worker.join(timeout=15)
                self.assertFalse(worker.is_alive())
        results = [outcomes.get_nowait(), outcomes.get_nowait()]
        self.assertCountEqual([item[0] for item in results], ['ok', 'conflict'])
        winner = next(item for item in results if item[0] == 'ok')
        material.refresh_from_db()
        self.assertEqual((material.nome, material.quantidade, material.unidade), winner[1:])
        self.assertIn((material.nome, material.quantidade, material.unidade),
                      [('Primeiro', Decimal('8'), 'g'), ('Segundo', Decimal('6'), 'kg')])
        self.assertEqual(material.versao, 2)
