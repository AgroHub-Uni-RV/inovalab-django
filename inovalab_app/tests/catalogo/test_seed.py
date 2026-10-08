from io import StringIO
from django.core.management import call_command
from django.test import TestCase
from inovalab_app.catalogo.models import Equipamento, Servico, ServicoLegado

class InitialServicesTests(TestCase):
    def test_bootstrap_only_seeds_equipment_not_requested_services(self):
        call_command('seed_inovalab', stdout=StringIO())
        self.assertEqual(Equipamento.objects.count(), 6)
        self.assertFalse(Servico.objects.exists())
        self.assertFalse(ServicoLegado.objects.exists())

    def test_retired_command_preserves_catalog_history_without_creating_requests(self):
        legacy = ServicoLegado.objects.create(nome='Serviço histórico', codigo_inicial='historico')
        call_command('carregar_servicos_iniciais', stdout=StringIO())
        call_command('seed_inovalab', stdout=StringIO())
        legacy.refresh_from_db()
        self.assertEqual(legacy.nome, 'Serviço histórico')
        self.assertFalse(Servico.objects.exists())

    def test_seed_keeps_local_equipment_edits_and_is_idempotent(self):
        equipment = Equipamento.objects.first()
        equipment.nome = 'Nome local'
        equipment.save()
        for _ in range(2):
            call_command('seed_inovalab', stdout=StringIO())
        equipment.refresh_from_db()
        self.assertEqual(equipment.nome, 'Nome local')
        self.assertEqual(Equipamento.objects.count(), 6)
