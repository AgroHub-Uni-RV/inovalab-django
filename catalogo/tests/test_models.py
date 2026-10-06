from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Group
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DataError, IntegrityError, transaction
from django.test import TestCase

from catalogo.models import Equipamento, Espaco, Servico
from catalogo.services import save_entry


class CatalogModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_user('gestor')
        cls.admin.groups.add(Group.objects.get(name='Administradores'))
        cls.user = get_user_model().objects.create_user('leitor', is_staff=True)

    def test_business_admin_without_staff_can_create_all_models(self):
        for model, data in ((Servico, {'nome': '  Serviço  '}),
                            (Equipamento, {'nome': 'Equipamento'}),
                            (Espaco, {'nome': 'Sala', 'capacidade_maxima_de_pessoas': 10})):
            with self.subTest(model=model):
                entry = save_entry(actor=self.admin, model=model, data=data)
                self.assertEqual(entry.status, 'disponivel')
                self.assertEqual(entry.nome, data['nome'].strip())
                self.assertIsNotNone(entry.pk)

    def test_anonymous_staff_and_inactive_admin_cannot_write(self):
        self.admin.is_active = False
        for actor in (AnonymousUser(), self.user, self.admin):
            with self.subTest(actor=actor), self.assertRaises(PermissionDenied):
                save_entry(actor=actor, model=Servico, data={'nome': 'Negado'})
        self.assertFalse(Servico.objects.filter(nome='Negado').exists())

    def test_names_are_trimmed_required_and_not_unique(self):
        for invalid in ('', '   ', 'a' * 151):
            with self.subTest(invalid=invalid), self.assertRaises(ValidationError):
                save_entry(actor=self.admin, model=Equipamento, data={'nome': invalid})
        for _ in range(2):
            save_entry(actor=self.admin, model=Equipamento, data={'nome': 'Mesmo nome'})
        self.assertEqual(Equipamento.objects.filter(nome='Mesmo nome').count(), 2)
        with self.assertRaises(ValidationError):
            Equipamento(nome='   ').full_clean()

    def test_status_choices_differ_between_services_and_resources(self):
        with self.assertRaises(ValidationError):
            save_entry(actor=self.admin, model=Servico, data={'nome': 'Serviço', 'status': 'ocupado'})
        for model, data in ((Equipamento, {'nome': 'Impressora'}),
                            (Espaco, {'nome': 'Sala', 'capacidade_maxima_de_pessoas': 3})):
            save_entry(actor=self.admin, model=model, data={**data, 'status': 'ocupado'})
            with self.assertRaises(ValidationError):
                save_entry(actor=self.admin, model=model, data={**data, 'status': 'inexistente'})

    def test_capacity_bounds_are_validated_and_constrained_in_database(self):
        for value in (0, -1, 2147483648):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                save_entry(actor=self.admin, model=Espaco, data={
                    'nome': 'Sala inválida', 'capacidade_maxima_de_pessoas': value,
                })
            # PostgreSQL rejeita overflow como DataError; SQLite usa a constraint.
            with self.subTest(database=value), self.assertRaises((DataError, IntegrityError)), transaction.atomic():
                Espaco.objects.create(nome='Sala inválida', capacidade_maxima_de_pessoas=value)
        for value in (1, 2147483647):
            Espaco(nome='Sala', capacidade_maxima_de_pessoas=value).full_clean()

    def test_invalid_update_does_not_persist_any_field(self):
        entry = save_entry(actor=self.admin, model=Espaco, data={
            'nome': 'Original', 'capacidade_maxima_de_pessoas': 10,
        })
        with self.assertRaises(ValidationError):
            save_entry(actor=self.admin, model=Espaco, instance=entry, data={
                'nome': 'Alterado', 'capacidade_maxima_de_pessoas': 0,
            })
        entry.refresh_from_db()
        self.assertEqual(entry.nome, 'Original')
        self.assertEqual(entry.capacidade_maxima_de_pessoas, 10)

    def test_capacity_original_value_is_validated_before_integer_coercion(self):
        entry = save_entry(actor=self.admin, model=Espaco, data={
            'nome': 'Original', 'capacidade_maxima_de_pessoas': 10,
        })
        for value in (1.5, Decimal('1.5'), True, False, float('inf'), float('nan')):
            with self.subTest(value=value, operation='create'), self.assertRaises(ValidationError):
                save_entry(actor=self.admin, model=Espaco, data={
                    'nome': 'Não criar', 'capacidade_maxima_de_pessoas': value,
                })
            with self.subTest(value=value, operation='update'), self.assertRaises(ValidationError):
                save_entry(actor=self.admin, model=Espaco, instance=entry, data={
                    'nome': 'Não editar', 'capacidade_maxima_de_pessoas': value,
                })
            with self.subTest(value=value, operation='model'), self.assertRaises(ValidationError):
                Espaco(nome='Não criar', capacidade_maxima_de_pessoas=value).full_clean()
            entry.refresh_from_db()
            self.assertEqual(entry.nome, 'Original')
            self.assertEqual(entry.capacidade_maxima_de_pessoas, 10)
        self.assertEqual(Espaco.objects.count(), 10)

    def test_private_seed_key_cannot_be_changed_by_write_operation(self):
        entry = Servico.objects.first()
        original_key = entry.codigo_inicial
        with self.assertRaises(ValidationError):
            save_entry(actor=self.admin, model=Servico, instance=entry, data={'codigo_inicial': 'outro'})
        entry.refresh_from_db()
        self.assertEqual(entry.codigo_inicial, original_key)

    def test_database_rejects_invalid_status(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Equipamento.objects.create(nome='Inválido', status='outro')
