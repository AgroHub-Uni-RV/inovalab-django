from datetime import date, time, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404
from django.test import TestCase

from inovalab_app.agenda import services
from inovalab_app.agenda.models import AgendaVisita


class VisitExecutionServiceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.admin = User.objects.create_superuser('realizacao-admin')
        cls.staff = User.objects.create_user('realizacao-equipe', is_staff=True)
        cls.external = User.objects.create_user('realizacao-titular')
        cls.inactive = User.objects.create_superuser('realizacao-inativo', is_active=False)

    def setUp(self):
        self.visit = AgendaVisita.objects.create(quantidade_pessoas=2, data=date(2026, 10, 8),
            hora_inicio=time(9), hora_termino=time(10), criado_por=self.external)
        self.enterContext(patch('django.utils.timezone.now', return_value=self.visit.inicio))

    def mark(self, **changes):
        return services.mark_visit_realized(**{'actor': self.admin, 'booking_id': self.visit.pk,
                                               'expected_version': 1, **changes})

    def test_only_active_admin_can_mark_from_start(self):
        from inovalab_app.agenda.policies import can_mark_visit_realized
        for actor in (self.staff, self.external, self.inactive, AnonymousUser()):
            with self.assertRaises(PermissionDenied):
                self.mark(actor=actor)
            self.assertFalse(can_mark_visit_realized(actor, self.visit, now=self.visit.inicio))
        with patch('django.utils.timezone.now', return_value=self.visit.inicio-timedelta(seconds=1)):
            with self.assertRaises(ValidationError):
                self.mark()
        self.assertTrue(can_mark_visit_realized(self.admin, self.visit, now=self.visit.inicio))
        self.assertEqual(self.mark().realizada_em, self.visit.inicio)

    def test_realization_is_atomic_versioned_and_audited(self):
        saved = self.mark()
        self.assertEqual((saved.versao, saved.situacao, saved.criado_por_id, saved.avaliado_por_id),
                         (2, 'confirmado', self.external.pk, None))
        self.assertEqual((saved.realizada_por_id, saved.realizada_em), (self.admin.pk, self.visit.inicio))
        event = saved.eventos.get(acao='realizar')
        self.assertEqual(event.ator_id, self.admin.pk)
        self.assertEqual(event.alteracoes['realizada_por'], {'anterior': None, 'novo': self.admin.pk})

    def test_repeat_and_invalid_version_never_write(self):
        for version in (None, True, '1', 0, -1):
            with self.assertRaises(ValidationError):
                self.mark(expected_version=version)
        with self.assertRaises(services.BookingConflict):
            self.mark(expected_version=2)
        for situation in ('pendente', 'rejeitado'):
            AgendaVisita.objects.filter(pk=self.visit.pk).update(situacao=situation)
            with self.assertRaises(services.BookingConflict):
                self.mark()
        AgendaVisita.objects.filter(pk=self.visit.pk).update(situacao='confirmado', cancelado_em=self.visit.inicio)
        with self.assertRaises(Http404):
            self.mark()
        AgendaVisita.objects.filter(pk=self.visit.pk).update(cancelado_em=None)
        self.mark()
        for version in (1, 2):
            with self.assertRaises(services.BookingConflict):
                self.mark(expected_version=version)
        self.assertEqual(self.visit.eventos.count(), 1)

    def test_event_failure_rolls_back_realization(self):
        with patch('inovalab_app.agenda.services._record', side_effect=RuntimeError('Falha ao registrar')):
            with self.assertRaises(RuntimeError):
                self.mark()
        self.visit.refresh_from_db()
        self.assertEqual((self.visit.versao, self.visit.realizada_em, self.visit.realizada_por_id), (1, None, None))
        self.assertFalse(self.visit.eventos.exists())

    def test_schedule_edit_cannot_move_start_after_realization(self):
        self.mark()
        with self.assertRaises(ValidationError):
            services.save_booking(actor=self.admin, category='visita', booking_id=self.visit.pk,
                expected_version=2, data={'hora_inicio': time(9, 30)})
        saved = services.save_booking(actor=self.admin, category='visita', booking_id=self.visit.pk,
            expected_version=2, data={'observacoes': 'Registro preservado'})
        self.assertEqual((saved.versao, saved.realizada_em), (3, self.visit.inicio))
        self.assertEqual(saved.observacoes, 'Registro preservado')

    def test_actor_deletion_preserves_realization_and_history(self):
        saved = self.mark()
        self.admin.delete()
        saved.refresh_from_db()
        self.assertIsNone(saved.realizada_por_id)
        self.assertEqual(saved.realizada_em, self.visit.inicio)
        self.assertEqual(saved.eventos.get().ator_nome, 'realizacao-admin')
        self.assertEqual(saved.estado_execucao, 'concluido')

    def test_authorized_cancellation_preserves_realization(self):
        self.mark()
        saved = services.cancel_booking(actor=self.admin, category='visita', booking_id=self.visit.pk, expected_version=2)
        self.assertEqual((saved.versao, saved.realizada_em, saved.estado_execucao),
                         (3, self.visit.inicio, 'nao_aplicavel'))
