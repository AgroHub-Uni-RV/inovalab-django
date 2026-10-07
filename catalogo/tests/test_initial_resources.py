from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from catalogo.models import Equipamento


class InitialResourcesTests(TestCase):
    def test_equipment_matches_supplied_images(self):
        self.assertEqual(set(Equipamento.objects.values_list('nome', flat=True)), {
            'Plotter de impressão', 'Impressora 3D', 'Corte a laser', 'Plotter de corte',
            'Óculos de realidade virtual', 'Scanner 3D manual',
        })
        self.assertFalse(Equipamento.objects.exclude(status='disponivel').exists())
        for entry in Equipamento.objects.all():
            entry.full_clean()

    def test_command_preserves_edited_equipment(self):
        machine = Equipamento.objects.get(codigo_inicial='impressora-3d')
        machine.nome = 'Nome local'
        machine.status = 'indisponivel'
        machine.save()
        for _ in range(2):
            call_command('carregar_recursos_iniciais', stdout=StringIO())
        machine.refresh_from_db()
        self.assertEqual((machine.nome, machine.status), ('Nome local', 'indisponivel'))
        self.assertEqual(Equipamento.objects.count(), 6)

    def test_command_restores_missing_seed_and_keeps_custom_entries(self):
        Equipamento.objects.get(codigo_inicial='impressora-3d').delete()
        custom = Equipamento.objects.create(nome='Máquina local')
        call_command('carregar_recursos_iniciais', stdout=StringIO())
        self.assertEqual(Equipamento.objects.count(), 7)
        custom.refresh_from_db()
        self.assertIsNone(custom.codigo_inicial)
