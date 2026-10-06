from datetime import datetime, timedelta, timezone as dt_timezone

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Group
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, connection
from django.db.models.deletion import ProtectedError
from django.test import TestCase

from agenda.models import Agendamento, EventoAgendamento
from agenda.services import BookingConflict, cancel_booking, save_booking
from catalogo.models import Equipamento, Espaco, Servico
from integracoes.credentials import CredentialRejected, authenticate_token
from integracoes.models import ClienteIntegracao, PedidoIntegracao
from integracoes.selectors import visible_clients
from integracoes.services import create_client, receive_booking, rotate_credential, update_client


class IntegrationServiceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_user('gestor')
        cls.admin.groups.add(Group.objects.get(name='Administradores'))
        cls.user = get_user_model().objects.create_user('staff', is_staff=True)
        cls.service = Servico.objects.first()
        cls.equipment = Equipamento.objects.create(nome='Impressora')
        cls.space = Espaco.objects.create(nome='Sala', capacidade_maxima_de_pessoas=8)

    def setUp(self):
        self.client, self.token = create_client(actor=self.admin, name='AgroHub')
        self.principal = authenticate_token(self.token)
        self.data = {'id_externo': 'pedido-001', 'requerente_id': 'pessoa-45', 'requerente': 'Ana', 'motivo': 'Protótipo',
                     'categoria': 'servico', 'objeto': self.service.pk,
                     'inicio': datetime.fromisoformat('2026-11-01T14:00:00-03:00'),
                     'fim': datetime.fromisoformat('2026-11-01T15:00:00-03:00')}

    def receive(self, **overrides):
        return receive_booking(principal=self.principal, data={**self.data, **overrides})

    def test_credential_is_hashed_unique_and_does_not_create_internal_account(self):
        self.assertNotEqual(self.client.token_digest, self.token)
        self.assertEqual(len(self.client.token_digest), 64)
        self.assertEqual(self.principal.cliente_id, self.client.pk)
        self.assertEqual(get_user_model().objects.count(), 2)
        other, token = create_client(actor=self.admin, name='Outro sistema')
        self.assertNotEqual(other.token_digest, self.client.token_digest)
        self.assertNotEqual(token, self.token)
        self.assertEqual(visible_clients(self.admin).count(), 2)
        for value in ('', 'inválido', self.token + 'a', self.token.replace('inovalab_', 'outro_')):
            with self.assertRaises(CredentialRejected):
                authenticate_token(value)

    def test_only_active_business_admin_can_manage_clients(self):
        self.admin.is_active = False
        for actor in (self.user, AnonymousUser(), self.admin):
            self.assertFalse(visible_clients(actor).exists())
            with self.assertRaises(PermissionDenied):
                create_client(actor=actor, name='Não criar')
            with self.assertRaises(PermissionDenied):
                update_client(actor=actor, client_id=self.client.pk, data={'ativo': False}, expected_version=1)
            with self.assertRaises(PermissionDenied):
                rotate_credential(actor=actor, client_id=self.client.pk, expected_version=1)

    def test_rotation_and_deactivation_invalidate_old_principals_and_reactivation_needs_new_secret(self):
        client, token = rotate_credential(actor=self.admin, client_id=self.client.pk, expected_version=1)
        self.assertEqual(client.versao, 2)
        with self.assertRaises(CredentialRejected):
            self.receive()
        with self.assertRaises(CredentialRejected):
            authenticate_token(self.token)
        self.principal = authenticate_token(token)
        update_client(actor=self.admin, client_id=client.pk, expected_version=2, data={'ativo': False})
        with self.assertRaises(CredentialRejected):
            self.receive()
        update_client(actor=self.admin, client_id=client.pk, expected_version=3, data={'ativo': True})
        with self.assertRaises(CredentialRejected):
            authenticate_token(token)
        client, new_token = rotate_credential(actor=self.admin, client_id=client.pk, expected_version=4)
        self.assertEqual(authenticate_token(new_token).cliente_id, client.pk)

    def test_client_versions_and_protected_fields_are_strict(self):
        update_client(actor=self.admin, client_id=self.client.pk, expected_version=1, data={'nome': 'Nome corrigido'})
        for operation in (lambda: rotate_credential(actor=self.admin, client_id=self.client.pk, expected_version=1),
                          lambda: update_client(actor=self.admin, client_id=self.client.pk, expected_version=1, data={'ativo': False})):
            with self.assertRaises(BookingConflict):
                operation()
        for version in (None, True, '2', 0, 2.5):
            with self.assertRaises(ValidationError):
                rotate_credential(actor=self.admin, client_id=self.client.pk, expected_version=version)
        for fields in ({'token_digest': 'a'}, {'identificador': 'a'}, {'criado_por': self.user.pk}, {'ativo': 'false'}):
            with self.assertRaises(ValidationError):
                update_client(actor=self.admin, client_id=self.client.pk, expected_version=2, data=fields)
        self.client.refresh_from_db()
        self.assertEqual((self.client.nome, self.client.ativo, self.client.versao), ('Nome corrigido', True, 2))

    def test_three_targets_create_one_linked_booking_with_external_actor(self):
        for index, (category, target) in enumerate((('servico', self.service), ('equipamento', self.equipment))):
            booking, receipt, repeated = self.receive(id_externo=str(index), categoria=category, objeto=target.pk)
            self.assertFalse(repeated)
            self.assertEqual((receipt.agendamento_id, receipt.cliente_id, receipt.requerente_id), (booking.pk, self.client.pk, 'pessoa-45'))
            self.assertIsNone(booking.criado_por_id)
            event = booking.eventos.get()
            self.assertIsNone(event.ator_id)
            self.assertEqual(event.ator_nome, 'Integração: AgroHub')

    def test_same_key_and_canonical_content_replays_original_booking(self):
        booking, receipt, repeated = self.receive()
        replay, same_receipt, repeated = self.receive(requerente='  Ana  ', motivo=' Protótipo ',
            inicio=self.data['inicio'].astimezone(dt_timezone.utc), fim=self.data['fim'].astimezone(dt_timezone.utc))
        self.assertTrue(repeated)
        self.assertEqual((replay.pk, same_receipt.pk), (booking.pk, receipt.pk))
        self.assertEqual((Agendamento.objects.count(), PedidoIntegracao.objects.count(), EventoAgendamento.objects.count()), (1, 1, 1))

    def test_same_key_different_content_is_conflict_and_client_namespaces_are_independent(self):
        self.receive()
        for fields in ({'motivo': 'Outro'}, {'requerente_id': 'outra-pessoa'}, {'objeto': self.equipment.pk, 'categoria': 'equipamento'}):
            with self.assertRaises(BookingConflict) as error:
                self.receive(**fields)
            self.assertEqual(error.exception.code, 'idempotencia_conflitante')
        other, token = create_client(actor=self.admin, name='Outro')
        receive_booking(principal=authenticate_token(token), data={**self.data, 'categoria': 'equipamento', 'objeto': self.equipment.pk})
        self.assertEqual(PedidoIntegracao.objects.count(), 2)

    def test_replay_after_admin_edit_deactivation_or_cancellation_never_recreates(self):
        booking, receipt, _ = self.receive()
        save_booking(actor=self.admin, booking_id=booking.pk, expected_version=1, data={'motivo': 'Editado localmente'})
        self.service.status = 'indisponivel'
        self.service.save()
        replay, _, repeated = self.receive()
        self.assertTrue(repeated)
        self.assertEqual((replay.motivo, replay.versao), ('Editado localmente', 2))
        cancel_booking(actor=self.admin, booking_id=booking.pk, expected_version=2)
        replay, _, repeated = self.receive()
        self.assertEqual((replay.pk, replay.versao, repeated), (booking.pk, 3, True))
        self.assertIsNotNone(replay.cancelado_em)
        self.assertEqual(Agendamento.objects.count(), 1)

    def test_invalid_and_protected_payload_never_creates_booking_or_receipt(self):
        for fields in ({'id_externo': ''}, {'id_externo': 1}, {'requerente_id': ' '}, {'requerente': 'A' * 151},
                       {'categoria': 'qualquer'}, {'objeto': True}, {'fim': self.data['inicio']},
                       {'inicio': self.data['inicio'].replace(tzinfo=None)}, {'versao': 1}, {'cliente': self.client.pk}):
            with self.subTest(fields=fields), self.assertRaises(ValidationError):
                self.receive(**fields)
        with self.assertRaises(ValidationError):
            receive_booking(principal=self.principal, data={})
        with self.assertRaises(CredentialRejected):
            receive_booking(principal=self.admin, data=self.data)
        self.assertEqual((Agendamento.objects.count(), PedidoIntegracao.objects.count()), (0, 0))

    def test_overlap_unavailable_and_nonexistent_targets_do_not_record_request(self):
        self.receive()
        with self.assertRaises(BookingConflict) as error:
            self.receive(id_externo='outro')
        self.assertEqual(error.exception.code, 'horario_ocupado')
        self.equipment.status = 'indisponivel'
        self.equipment.save()
        for fields in ({'categoria': 'equipamento', 'objeto': self.equipment.pk}, {'objeto': 999999}):
            with self.assertRaises(ValidationError):
                self.receive(id_externo='outro', **fields)
        self.assertEqual(PedidoIntegracao.objects.count(), 1)

    def test_request_insert_failure_rolls_back_booking_and_history(self):
        def fail_receipt(execute, sql, params, many, context):
            if 'INSERT INTO "integracoes_pedidointegracao"' in sql:
                raise IntegrityError('Falha simulada no pedido')
            return execute(sql, params, many, context)
        with connection.execute_wrapper(fail_receipt), self.assertRaises(IntegrityError):
            self.receive()
        self.assertEqual((Agendamento.objects.count(), PedidoIntegracao.objects.count(), EventoAgendamento.objects.count()), (0, 0, 0))

    def test_external_booking_and_client_remain_protected(self):
        booking, receipt, _ = self.receive()
        with self.assertRaises(ProtectedError):
            booking.delete()
        with self.assertRaises(ProtectedError):
            self.client.delete()

    def test_historical_fold_is_compared_and_canonicalized_as_real_utc_instants(self):
        booking, _, _ = self.receive(inicio=datetime.fromisoformat('2019-02-16T23:30:00-02:00'),
                                    fim=datetime.fromisoformat('2019-02-16T23:15:00-03:00'))
        self.assertEqual(booking.fim - booking.inicio, timedelta(minutes=45))
        with self.assertRaises(BookingConflict) as error:
            self.receive(inicio=datetime.fromisoformat('2019-02-16T23:30:00-03:00'),
                         fim=datetime.fromisoformat('2019-02-17T01:00:00-03:00'))
        self.assertEqual(error.exception.code, 'idempotencia_conflitante')
