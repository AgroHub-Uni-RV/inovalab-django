from importlib import import_module
from io import StringIO

from django.apps import apps
from django.core.management import call_command
from django.db import connection
from django.test import TestCase

from catalogo.models import Equipamento, Espaco


class InitialResourcesTests(TestCase):
    def test_equipment_and_spaces_match_supplied_images(self):
        self.assertEqual(set(Equipamento.objects.values_list('nome', flat=True)), {
            'Plotter de impressão', 'Impressora 3D', 'Corte a laser', 'Plotter de corte',
            'Óculos de realidade virtual', 'Scanner 3D manual',
        })
        self.assertEqual(dict(Espaco.objects.values_list('nome', 'capacidade_maxima_de_pessoas')), {
            'Secretaria': None, 'Sala 01': 4, 'Sala 02': 4, 'Área de convivência': 24,
            'Sala 03': 4, 'Sala 04': 4, 'Espaço de coworking': 40,
            'Laboratório maker': None, 'Laboratório de robótica': None,
        })
        self.assertEqual(set(Espaco.objects.filter(somente_administradores=True).values_list('nome', flat=True)), {
            'Secretaria', 'Laboratório maker', 'Laboratório de robótica',
        })
        for model in (Equipamento, Espaco):
            self.assertFalse(model.objects.exclude(status='disponivel').exists())
            for entry in model.objects.all():
                entry.full_clean()

    def test_command_and_frozen_migration_preserve_edited_resources(self):
        machine = Equipamento.objects.get(codigo_inicial='impressora-3d')
        machine.nome = 'Nome local'
        machine.status = 'indisponivel'
        machine.save()
        room = Espaco.objects.get(codigo_inicial='laboratorio-maker')
        room.capacidade_maxima_de_pessoas = 12
        room.save()
        for _ in range(2):
            call_command('carregar_recursos_iniciais', stdout=StringIO())
            import_module('catalogo.migrations.0004_carga_maquinas_e_espacos').load_resources(
                apps, connection.schema_editor(),
            )
        machine.refresh_from_db()
        room.refresh_from_db()
        self.assertEqual((machine.nome, machine.status), ('Nome local', 'indisponivel'))
        self.assertEqual(room.capacidade_maxima_de_pessoas, 12)
        self.assertTrue(room.somente_administradores)
        self.assertEqual((Equipamento.objects.count(), Espaco.objects.count()), (6, 9))

    def test_command_restores_missing_seed_and_keeps_custom_entries(self):
        Equipamento.objects.get(codigo_inicial='impressora-3d').delete()
        Espaco.objects.get(codigo_inicial='sala-01').delete()
        custom = Equipamento.objects.create(nome='Máquina local')
        call_command('carregar_recursos_iniciais', stdout=StringIO())
        self.assertEqual((Equipamento.objects.count(), Espaco.objects.count()), (7, 9))
        custom.refresh_from_db()
        self.assertIsNone(custom.codigo_inicial)
