from datetime import datetime, timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Group
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase

from agenda import services
from agenda.models import Agendamento
from agenda.selectors import calendar_weeks, visible_bookings
from catalogo.models import Equipamento, Espaco, Servico
from materiais.models import Material


class BookingRequestTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_user('avaliador')
        cls.admin.groups.add(Group.objects.get(name='Administradores'))
        cls.user = get_user_model().objects.create_user('solicitante', is_staff=True)
        cls.other = get_user_model().objects.create_user('outro')
        cls.service = Servico.objects.first()
        cls.machine = Equipamento.objects.create(nome='Máquina para pedido')
        cls.material = Material.objects.create(nome='PLA pedido', categoria='Filamento', quantidade=500,
                                               unidade='g', fonte='Laboratório')
        cls.data = {'categoria': 'servico', 'objeto': cls.service.pk, 'requerente': 'Nome informado',
                    'motivo': 'Pedido próprio', 'material_proprio': True,
                    'inicio': datetime.fromisoformat('2026-11-01T14:00:00-03:00'),
                    'fim': datetime.fromisoformat('2026-11-01T15:00:00-03:00')}

    def create(self, actor=None, **overrides):
        return services.save_booking(actor=actor or self.user, data={**self.data, **overrides})

    def review(self, booking, decision='aprovar', actor=None, version=1):
        return services.review_booking(actor=actor or self.admin, booking_id=booking.pk,
                                       expected_version=version, decision=decision)

    def test_normal_creation_is_pending_and_owned(self):
        try:
            booking = self.create()
        except PermissionDenied:
            self.fail('Usuário ativo deve conseguir solicitar um agendamento.')
        self.assertEqual((booking.situacao, booking.criado_por_id), ('pendente', self.user.pk))
        self.assertIsNone(booking.avaliado_em)
        self.assertEqual(list(visible_bookings(self.user)), [booking])
        self.assertEqual(list(visible_bookings(self.other)), [])
        self.assertEqual(booking.eventos.get().ator_id, self.user.pk)

    def test_pending_requests_do_not_block_confirmed_creation_or_calendar(self):
        first = self.create()
        self.create(actor=self.other)
        confirmed = self.create(actor=self.admin)
        days = [day for week in calendar_weeks(visible_bookings(self.admin), '2026-11') for day in week]
        self.assertEqual(sum(day['count'] for day in days), 1)
        self.assertEqual([booking.pk for day in days for booking in day['bookings']], [confirmed.pk])
        first.refresh_from_db()
        self.assertEqual(first.situacao, 'pendente')

    def test_pending_request_can_be_created_over_existing_confirmed_booking(self):
        self.create(actor=self.admin)
        self.assertEqual(self.create().situacao, 'pendente')

    def test_approval_reserves_and_records_decision_without_changing_owner(self):
        booking = self.create()
        saved = self.review(booking)
        self.assertEqual((saved.situacao, saved.versao, saved.criado_por_id, saved.avaliado_por_id),
                         ('confirmado', 2, self.user.pk, self.admin.pk))
        self.assertIsNotNone(saved.avaliado_em)
        event = saved.eventos.first()
        self.assertEqual((event.acao, event.ator_id), ('aprovar', self.admin.pk))
        self.assertEqual(event.alteracoes['situacao'], {'anterior': 'pendente', 'novo': 'confirmado'})
        with self.assertRaises(services.BookingConflict):
            self.create(actor=self.admin)

    def test_approval_conflict_keeps_pending_and_does_not_record_decision(self):
        booking = self.create()
        self.create(actor=self.admin)
        with self.assertRaises(services.BookingConflict) as error:
            self.review(booking)
        self.assertEqual(error.exception.code, 'horario_ocupado')
        booking.refresh_from_db()
        self.assertEqual((booking.situacao, booking.versao, booking.eventos.count()), ('pendente', 1, 1))
        self.assertIsNone(booking.avaliado_em)

    def test_rejection_remains_visible_without_reserving_or_requiring_free_slot(self):
        booking = self.create()
        self.create(actor=self.admin)
        saved = self.review(booking, 'rejeitar')
        self.assertEqual((saved.situacao, saved.versao), ('rejeitado', 2))
        self.assertIn(saved, visible_bookings(self.user))
        self.assertEqual(saved.eventos.first().acao, 'rejeitar')

    def test_decisions_are_admin_only_and_cannot_be_repeated(self):
        booking = self.create()
        for actor in (self.user, self.other, AnonymousUser()):
            with self.assertRaises(PermissionDenied):
                self.review(booking, actor=actor)
        self.review(booking, 'rejeitar')
        for version in (1, 2):
            with self.assertRaises(services.BookingConflict):
                self.review(booking, version=version)
        self.assertEqual(booking.eventos.count(), 2)

    def test_invalid_decision_and_stale_or_invalid_versions_do_not_change_request(self):
        booking = self.create()
        with self.assertRaises(ValidationError):
            self.review(booking, decision='confirmado')
        for version in (None, True, '1', 0):
            with self.assertRaises(ValidationError):
                self.review(booking, version=version)
        services.save_booking(actor=self.admin, booking_id=booking.pk, expected_version=1,
                              data={'motivo': 'Pedido corrigido pelo administrador'})
        with self.assertRaises(services.BookingConflict):
            self.review(booking)
        booking.refresh_from_db()
        self.assertEqual((booking.situacao, booking.versao), ('pendente', 2))

    def test_normal_user_cannot_edit_cancel_or_assign_protected_fields(self):
        booking = self.create()
        with self.assertRaises(PermissionDenied):
            services.save_booking(actor=self.user, booking_id=booking.pk, expected_version=1, data={'motivo': 'Editar'})
        with self.assertRaises(PermissionDenied):
            services.cancel_booking(actor=self.user, booking_id=booking.pk, expected_version=1)
        for field in ('situacao', 'criado_por', 'avaliado_por', 'avaliado_em'):
            with self.assertRaises(ValidationError):
                self.create(**{field: 'confirmado'})

    def test_anonymous_and_inactive_have_no_access(self):
        self.create()
        self.user.is_active = False
        for actor in (self.user, AnonymousUser()):
            self.assertFalse(visible_bookings(actor).exists())
            with self.assertRaises(PermissionDenied):
                self.create(actor=actor)

    def test_restricted_spaces_remain_admin_only(self):
        for space in Espaco.objects.filter(somente_administradores=True):
            fields = {'categoria': 'espaco', 'objeto': space.pk, 'material_proprio': None}
            with self.assertRaises(PermissionDenied):
                self.create(**fields)
            self.assertEqual(self.create(actor=self.admin, **fields).situacao, 'confirmado')

    def test_approval_revalidates_target_machine_and_material_availability(self):
        for resource in (self.service, self.machine, self.material):
            booking = self.create(equipamentos=[self.machine.pk], material_proprio=False,
                                  material_gasto=self.material.pk, material_gasto_gramas=12)
            type(resource).objects.filter(pk=resource.pk).update(status='indisponivel')
            with self.assertRaises(ValidationError):
                self.review(booking)
            booking.refresh_from_db()
            self.assertEqual((booking.situacao, booking.eventos.count()), ('pendente', 1))
            type(resource).objects.filter(pk=resource.pk).update(status='disponivel')

    def test_adjacent_approval_and_optional_service_machines_preserve_reservation_rules(self):
        booking = self.create(equipamentos=[self.machine.pk])
        self.create(actor=self.admin, categoria='equipamento', objeto=self.machine.pk, material_proprio=None)
        self.review(booking)
        adjacent = self.create(inicio=self.data['fim'], fim=self.data['fim'] + timedelta(hours=1))
        self.assertEqual(self.review(adjacent).situacao, 'confirmado')

    def test_admin_and_legacy_direct_creation_are_confirmed_without_evaluator(self):
        booking = self.create(actor=self.admin)
        self.assertEqual(booking.situacao, 'confirmado')
        self.assertIsNone(booking.avaliado_por_id)
        legacy = Agendamento.objects.create(servico=self.service, requerente='Existente', motivo='Importado',
                                            inicio=self.data['inicio'], fim=self.data['fim'])
        self.assertEqual(legacy.situacao, 'confirmado')
