from io import StringIO
from importlib import import_module

from django.apps import apps
from django.core.management import call_command
from django.db import connection
from django.test import TestCase

from catalogo.models import Equipamento, Servico


EXPECTED_SERVICES = {
    'Identidade Visual': '', 'Impressão Sublimática': '', 'Criação de Banners': '',
    'Impressão 3D': 'Modelagem e Impressão 3D.',
    'Corte a laser': 'Cortes e gravações em diversos materiais.',
    'Plotter de recorte': 'Recorte de vinil adesivo e outros materiais.',
    'Óculos de realidade virtual': 'Dispositivos para experiências imersivas.',
    'Scanner 3D manual': 'Digitalização de objetos para 3D.',
    'Plotter de Impressão': 'Imprima em alta qualidade.',
    'Consultoria técnica': 'Suporte e orientação para o desenvolvimento do projeto.',
    'Uso do espaço': 'Uso do espaço para aula, demonstração e outros.',
}


class InitialServicesTests(TestCase):
    def test_migration_loads_exact_pdf_services(self):
        self.assertEqual(dict(Servico.objects.values_list('nome', 'descricao')), EXPECTED_SERVICES)
        self.assertEqual(Servico.objects.count(), 11)
        self.assertEqual(Servico.objects.filter(status='disponivel').count(), 11)
        self.assertEqual(Servico.objects.exclude(codigo_inicial=None).count(), 11)
        self.assertEqual(Equipamento.objects.count(), 6)

    def test_command_and_migration_are_idempotent_and_preserve_edits(self):
        entry = Servico.objects.get(nome='Impressão 3D')
        original_pk = entry.pk
        entry.nome = 'Prototipagem'
        entry.descricao = 'Descrição local'
        entry.status = 'indisponivel'
        entry.save()
        for _ in range(2):
            call_command('carregar_servicos_iniciais', stdout=StringIO())
            import_module('catalogo.migrations.0002_initial_services').load_services(apps, connection.schema_editor())
        entry.refresh_from_db()
        self.assertEqual(entry.pk, original_pk)
        self.assertEqual(entry.nome, 'Prototipagem')
        self.assertEqual(entry.descricao, 'Descrição local')
        self.assertEqual(entry.status, 'indisponivel')
        self.assertEqual(Servico.objects.count(), 11)
        self.assertFalse(Servico.objects.filter(nome='Impressão 3D').exists())

    def test_command_restores_only_missing_seed_and_preserves_custom_services(self):
        Servico.objects.get(nome='Impressão 3D').delete()
        custom = Servico.objects.create(nome='Serviço local', descricao='Personalizado')
        call_command('carregar_servicos_iniciais', stdout=StringIO())
        self.assertEqual(Servico.objects.count(), 12)
        self.assertEqual(Servico.objects.get(nome='Impressão 3D').descricao, EXPECTED_SERVICES['Impressão 3D'])
        custom.refresh_from_db()
        self.assertIsNone(custom.codigo_inicial)
        self.assertEqual(custom.descricao, 'Personalizado')
