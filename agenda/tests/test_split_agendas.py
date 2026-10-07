from datetime import datetime
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from agenda import models
from agenda.services import save_booking, cancel_booking
from agenda.selectors import visible_bookings, visible_booking
from catalogo.models import Servico, Equipamento


class SplitAgendaTests(TestCase):
    def setUp(self):
        self.assertTrue(hasattr(models, 'AgendaServico'), 'Falta a agenda concreta de serviços')
        self.admin = get_user_model().objects.create_user('gestor-split')
        self.admin.groups.add(Group.objects.get(name='Administradores'))
        self.service = Servico.objects.first()
        self.equipment = Equipamento.objects.create(nome='Máquina split')
        base = dict(pk=77, motivo='Original', criado_por=self.admin,
                    inicio=datetime.fromisoformat('2026-11-01T14:00:00-03:00'),
                    fim=datetime.fromisoformat('2026-11-01T15:00:00-03:00'))
        self.service_booking = models.AgendaServico.objects.create(servico=self.service, **base)
        self.equipment_booking = models.AgendaEquipamento.objects.create(equipamento=self.equipment, **base)

    def test_typed_edit_and_cancel_preserve_other_category_with_same_id(self):
        changed = save_booking(actor=self.admin, category='servico', booking_id=77,
                               expected_version=1, data={'motivo': 'Serviço alterado'})
        self.equipment_booking.refresh_from_db()
        self.assertEqual(changed.motivo, 'Serviço alterado')
        self.assertEqual(self.equipment_booking.motivo, 'Original')
        cancel_booking(actor=self.admin, category='equipamento', booking_id=77, expected_version=1)
        self.service_booking.refresh_from_db()
        self.assertIsNone(self.service_booking.cancelado_em)
        self.assertEqual(changed.eventos.get().acao, 'editar')
        self.assertEqual(self.equipment_booking.eventos.get().acao, 'cancelar')

    def test_typed_details_and_list_do_not_mix_equal_ids(self):
        self.client.force_login(self.admin)
        for category, name in [('servico', self.service.nome), ('equipamento', 'Máquina split')]:
            response = self.client.get(reverse('agenda:detail', kwargs={'category': category, 'pk': 77}))
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, name)
        rows = visible_bookings(self.admin)
        self.assertIsInstance(rows, list)
        self.assertEqual({(row.categoria, row.pk) for row in rows}, {('servico', 77), ('equipamento', 77)})

    def test_category_is_immutable_and_visits_require_complete_fields(self):
        with self.assertRaises(ValidationError):
            save_booking(actor=self.admin, category='servico', booking_id=77, expected_version=1,
                         data={'categoria': 'equipamento', 'objeto': self.equipment.pk})
        with self.assertRaises(ValidationError):
            save_booking(actor=self.admin, data={'categoria': 'visita'})
        self.assertEqual(models.AgendaServico.objects.count(), 1)
        self.assertEqual(models.AgendaEquipamento.objects.count(), 1)

    def test_typed_detail_queries_only_the_requested_agenda(self):
        with CaptureQueriesContext(connection) as queries:
            selected = visible_booking(self.admin, 'servico', 77)
        self.assertEqual(selected.pk, self.service_booking.pk)
        self.assertFalse(any('FROM "agenda_agendaequipamento"' in query['sql'] for query in queries))
