from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from inovalab_app.catalogo.models import Equipamento
from inovalab_app.catalogo.services import delete_equipment


class PublicServicesEquipmentTests(TestCase):
    def test_services_display_active_database_equipment_with_description_and_photo(self):
        custom = Equipamento.objects.create(nome='Equipamento personalizado público', descricao='Descrição do cadastro')
        machine = Equipamento.objects.get(codigo_inicial='impressora-3d')
        response = self.client.get('/servicos/')
        self.assertContains(response, custom.nome)
        self.assertContains(response, custom.descricao)
        self.assertContains(response, machine.nome)
        self.assertContains(response, reverse('conteudo:equipment-photo', args=[machine.pk]))
        self.assertContains(response, 'Sem foto')
        admin = get_user_model().objects.create_superuser('gestor-servicos-publicos')
        delete_equipment(actor=admin, equipment_id=custom.pk)
        self.assertNotContains(self.client.get('/servicos/'), custom.nome)

    def test_services_have_empty_state_when_catalogue_is_empty(self):
        from django.utils import timezone
        Equipamento.objects.update(excluido_em=timezone.now())
        self.assertContains(self.client.get('/servicos/'), 'Nenhum equipamento cadastrado no momento.')
