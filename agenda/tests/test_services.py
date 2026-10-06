from datetime import datetime, timedelta, timezone as dt_timezone

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Group
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, connection, transaction
from django.db.models.deletion import ProtectedError
from django.http import Http404
from django.test import TestCase

from catalogo.models import Equipamento, Espaco, Servico
from agenda.models import Agendamento, EventoAgendamento
from agenda.selectors import visible_bookings
from agenda.services import BookingConflict, cancel_booking, save_booking


class BookingServiceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_user('gestor')
        cls.admin.groups.add(Group.objects.get(name='Administradores'))
        cls.user = get_user_model().objects.create_user('comum', is_staff=True)
        cls.service = Servico.objects.first()
        cls.equipment = Equipamento.objects.create(nome='Impressora')
        cls.space = Espaco.objects.create(nome='Sala', capacidade_maxima_de_pessoas=8)
        cls.start = datetime.fromisoformat('2026-11-01T14:00:00-03:00')
        cls.end = datetime.fromisoformat('2026-11-01T15:00:00-03:00')

    def create_booking(self, **overrides):
        return save_booking(actor=self.admin, data={
            'categoria': 'servico', 'objeto': self.service.pk,
            'motivo': 'Produzir protótipo',
            'inicio': self.start, 'fim': self.end, **overrides,
        })

    def test_three_categories_have_one_protected_target_and_actor_event(self):
        for category, target in (('servico', self.service), ('equipamento', self.equipment), ('espaco', self.space)):
            booking = self.create_booking(categoria=category, objeto=target.pk)
            self.assertEqual((booking.categoria, booking.objeto_id, booking.versao), (category, target.pk, 1))
            self.assertEqual(sum(value is not None for value in (booking.servico_id, booking.equipamento_id, booking.espaco_id)), 1)
            self.assertEqual(booking.criado_por_id, self.admin.pk)
            self.assertEqual(booking.eventos.get().acao, 'criar')
            self.assertEqual(visible_bookings(self.admin).count(), Agendamento.objects.count())

    def test_anonymous_and_inactive_admin_cannot_read_or_write_and_staff_cannot_manage(self):
        booking = self.create_booking()
        self.admin.is_active = False
        for actor in (AnonymousUser(), self.admin):
            self.assertFalse(visible_bookings(actor).exists())
            with self.assertRaises(PermissionDenied):
                save_booking(actor=actor, data={})
            with self.assertRaises(PermissionDenied):
                cancel_booking(actor=actor, booking_id=booking.pk, expected_version=1)
        self.assertFalse(visible_bookings(self.user).exists())
        with self.assertRaises(PermissionDenied):
            save_booking(actor=self.user, booking_id=booking.pk, expected_version=1, data={'motivo': 'Alterar'})
        with self.assertRaises(PermissionDenied):
            cancel_booking(actor=self.user, booking_id=booking.pk, expected_version=1)

    def test_required_text_is_trimmed_and_invalid_data_does_not_create_events(self):
        booking = self.create_booking(motivo='  Protótipo  ')
        self.assertEqual(booking.motivo, 'Protótipo')
        for fields in ({'requerente': ' '}, {'motivo': ''}, {'requerente': 'A' * 151}, {'categoria': 'inexistente'},
                       {'objeto': 999999}, {'objeto': True}):
            with self.subTest(fields=fields), self.assertRaises(ValidationError):
                self.create_booking(**fields)
        self.assertEqual((Agendamento.objects.count(), EventoAgendamento.objects.count()), (1, 1))

    def test_database_enforces_exactly_one_target_and_positive_interval(self):
        base = {'motivo': 'Reserva', 'inicio': self.start, 'fim': self.end}
        for targets in ({}, {'servico': self.service, 'espaco': self.space}):
            with self.assertRaises(IntegrityError), transaction.atomic():
                Agendamento.objects.create(**base, **targets)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Agendamento.objects.create(**{**base, 'fim': self.start}, servico=self.service)

    def test_end_equal_before_start_and_naive_datetimes_are_rejected(self):
        for fields in ({'fim': self.start}, {'fim': self.start - timedelta(seconds=1)},
                       {'inicio': self.start.replace(tzinfo=None)}):
            with self.subTest(fields=fields), self.assertRaises(ValidationError):
                self.create_booking(**fields)
        self.assertEqual(Agendamento.objects.count(), 0)

    def test_each_category_is_exclusive_and_adjacent_slots_are_allowed(self):
        for category, target in (('servico', self.service), ('equipamento', self.equipment), ('espaco', self.space)):
            self.create_booking(categoria=category, objeto=target.pk)
            with self.assertRaises(BookingConflict) as error:
                self.create_booking(categoria=category, objeto=target.pk, inicio=self.start + timedelta(minutes=30))
            self.assertEqual(error.exception.code, 'horario_ocupado')
            self.create_booking(categoria=category, objeto=target.pk, inicio=self.end, fim=self.end + timedelta(hours=1))
        self.assertEqual(Agendamento.objects.count(), 6)

    def test_equal_ids_in_different_categories_do_not_conflict_and_other_objects_are_free(self):
        self.create_booking()
        self.create_booking(categoria='equipamento', objeto=self.equipment.pk)
        other = Servico.objects.create(nome='Outro serviço')
        self.create_booking(objeto=other.pk)
        self.assertEqual(Agendamento.objects.count(), 3)

    def test_unavailability_blocks_new_period_but_metadata_and_cancellation_preserve_old_reference(self):
        booking = self.create_booking(categoria='espaco', objeto=self.space.pk)
        self.space.status = 'indisponivel'
        self.space.save()
        with self.assertRaises(ValidationError):
            self.create_booking(categoria='espaco', objeto=self.space.pk, inicio=self.end, fim=self.end + timedelta(hours=1))
        booking = save_booking(actor=self.admin, booking_id=booking.pk, expected_version=1, data={'motivo': 'Manter vínculo'})
        with self.assertRaises(ValidationError):
            save_booking(actor=self.admin, booking_id=booking.pk, expected_version=2, data={'fim': self.end + timedelta(hours=1)})
        cancel_booking(actor=self.admin, booking_id=booking.pk, expected_version=2)
        self.space.refresh_from_db()
        self.assertEqual(self.space.status, 'indisponivel')

    def test_occupied_marker_does_not_block_future_reservation_or_change_catalog_status(self):
        self.equipment.status = 'ocupado'
        self.equipment.save()
        booking = self.create_booking(categoria='equipamento', objeto=self.equipment.pk)
        cancel_booking(actor=self.admin, booking_id=booking.pk, expected_version=1)
        self.equipment.refresh_from_db()
        self.assertEqual(self.equipment.status, 'ocupado')

    def test_edit_excludes_self_and_conflicting_update_keeps_all_original_fields(self):
        booking = self.create_booking()
        self.create_booking(inicio=self.end, fim=self.end + timedelta(hours=1))
        booking = save_booking(actor=self.admin, booking_id=booking.pk, expected_version=1,
                               data={'motivo': 'Corrigido', 'inicio': self.start, 'fim': self.end})
        with self.assertRaises(BookingConflict):
            save_booking(actor=self.admin, booking_id=booking.pk, expected_version=2,
                         data={'motivo': 'Não salvar', 'fim': self.end + timedelta(minutes=1)})
        booking.refresh_from_db()
        self.assertEqual((booking.motivo, booking.versao, booking.eventos.count()), ('Corrigido', 2, 2))

    def test_target_change_releases_old_object_and_validates_new_one(self):
        booking = self.create_booking()
        booking = save_booking(actor=self.admin, booking_id=booking.pk, expected_version=1,
                               data={'categoria': 'equipamento', 'objeto': self.equipment.pk})
        self.assertIsNone(booking.servico_id)
        self.assertEqual(booking.equipamento_id, self.equipment.pk)
        self.create_booking()
        with self.assertRaises(ValidationError):
            save_booking(actor=self.admin, booking_id=booking.pk, expected_version=2, data={'categoria': 'espaco'})

    def test_cancellation_hides_booking_preserves_history_and_releases_interval(self):
        booking = self.create_booking()
        cancel_booking(actor=self.admin, booking_id=booking.pk, expected_version=1)
        booking.refresh_from_db()
        self.assertIsNotNone(booking.cancelado_em)
        self.assertEqual((booking.versao, booking.eventos.count()), (2, 2))
        self.assertFalse(visible_bookings(self.admin).exists())
        with self.assertRaises(Http404):
            cancel_booking(actor=self.admin, booking_id=booking.pk, expected_version=2)
        self.create_booking()

    def test_old_version_and_protected_fields_never_persist_partially(self):
        booking = self.create_booking()
        save_booking(actor=self.admin, booking_id=booking.pk, expected_version=1, data={'motivo': 'Nova versão'})
        for operation in (lambda: save_booking(actor=self.admin, booking_id=booking.pk, expected_version=1, data={'motivo': 'Antiga'}),
                          lambda: cancel_booking(actor=self.admin, booking_id=booking.pk, expected_version=1)):
            with self.assertRaises(BookingConflict) as error:
                operation()
            self.assertEqual(error.exception.code, 'versao_desatualizada')
        for field in ('id', 'versao', 'cancelado_em', 'criado_por', 'servico', 'equipamento', 'espaco'):
            with self.subTest(field=field), self.assertRaises(ValidationError):
                save_booking(actor=self.admin, booking_id=booking.pk, expected_version=2, data={'motivo': 'Não salvar', field: 1})
        for version in (None, True, 0, -1, 1.5, '2'):
            with self.assertRaises(ValidationError):
                cancel_booking(actor=self.admin, booking_id=booking.pk, expected_version=version)
        booking.refresh_from_db()
        self.assertEqual((booking.motivo, booking.versao, booking.eventos.count()), ('Nova versão', 2, 2))

    def test_event_failure_rolls_back_create_and_edit(self):
        booking = self.create_booking()

        def failing_event(execute, sql, params, many, context):
            if 'INSERT INTO "agenda_eventoagendamento"' in sql:
                raise IntegrityError('Falha simulada ao persistir evento')
            return execute(sql, params, many, context)

        with connection.execute_wrapper(failing_event):
            with self.assertRaises(IntegrityError):
                save_booking(actor=self.admin, booking_id=booking.pk, expected_version=1, data={'motivo': 'Não persistir'})
            with self.assertRaises(IntegrityError):
                self.create_booking(inicio=self.end, fim=self.end + timedelta(hours=1))
        booking.refresh_from_db()
        self.assertEqual((booking.motivo, booking.versao, booking.eventos.count()), ('Produzir protótipo', 1, 1))
        self.assertEqual(Agendamento.objects.count(), 1)

    def test_equivalent_timezones_do_not_generate_false_date_changes(self):
        booking = self.create_booking()
        booking = save_booking(actor=self.admin, booking_id=booking.pk, expected_version=1, data={
            'motivo': 'Alteração real', 'inicio': self.start.astimezone(dt_timezone.utc), 'fim': self.end,
        })
        self.assertEqual(set(booking.eventos.get(acao='editar').alteracoes), {'motivo'})

    def test_cross_midnight_and_past_intervals_are_allowed(self):
        start = datetime.fromisoformat('2025-01-31T23:00:00-03:00')
        booking = self.create_booking(inicio=start, fim=start + timedelta(hours=2))
        self.assertEqual(booking.fim.day, 1)

    def test_referenced_objects_are_protected_including_cancelled_bookings(self):
        booking = self.create_booking()
        cancel_booking(actor=self.admin, booking_id=booking.pk, expected_version=1)
        with self.assertRaises(ProtectedError):
            self.service.delete()
