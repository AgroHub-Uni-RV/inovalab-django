from django.apps import apps
from django.test import SimpleTestCase


class ConsolidationRegistryTests(SimpleTestCase):
    def test_business_models_share_one_app_and_keep_physical_tables(self):
        expected = {
            'Servico': 'inovalab_servico_solicitado', 'ServicoLegado': 'catalogo_servico', 'Equipamento': 'catalogo_equipamento',
            'Material': 'materiais_material', 'Tarefa': 'tarefas_tarefa',
            'EventoTarefa': 'tarefas_eventotarefa', 'Banner': 'conteudo_banner',
            'AgendaServico': 'agenda_agendaservico',
            'AgendaEquipamento': 'agenda_agendaequipamento',
            'AgendaVisita': 'agenda_agendavisita',
            'EventoAgendamento': 'agenda_eventoagendamento',
        }
        config = apps.get_app_config('inovalab_app')
        self.assertEqual({model.__name__: model._meta.db_table for model in config.get_models()}, expected)
        self.assertEqual(apps.get_model('inovalab_app', 'AgendaServico')._meta.get_field('equipamentos').remote_field.through._meta.db_table,
                         'agenda_agendaservico_equipamentos')
        self.assertTrue(apps.is_installed('accounts'))
        for label in ('core', 'catalogo', 'materiais', 'tarefas', 'agenda', 'conteudo'):
            with self.assertRaises(LookupError):
                apps.get_app_config(label)
