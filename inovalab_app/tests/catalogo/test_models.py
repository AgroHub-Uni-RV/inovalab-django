from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Group
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from inovalab_app.catalogo.models import Equipamento, Servico
from inovalab_app.catalogo.services import save_entry


class CatalogModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_user('gestor')
        cls.admin.groups.add(Group.objects.get(name='Administradores'))
        cls.user = get_user_model().objects.create_user('leitor', is_staff=True)

    def test_business_admin_without_staff_can_create_all_models(self):
        for model, data in ((Servico, {'nome': '  Serviço  '}),
                            (Equipamento, {'nome': 'Equipamento'})):
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
        for model, data in ((Equipamento, {'nome': 'Impressora'}),):
            save_entry(actor=self.admin, model=model, data={**data, 'status': 'ocupado'})
            with self.assertRaises(ValidationError):
                save_entry(actor=self.admin, model=model, data={**data, 'status': 'inexistente'})

    def test_invalid_update_does_not_persist_any_field(self):
        entry = save_entry(actor=self.admin, model=Equipamento, data={
            'nome': 'Original', 'status': 'disponivel',
        })
        with self.assertRaises(ValidationError):
            save_entry(actor=self.admin, model=Equipamento, instance=entry, data={
                'nome': 'Alterado', 'status': 'inexistente',
            })
        entry.refresh_from_db()
        self.assertEqual(entry.nome, 'Original')
        self.assertEqual(entry.status, 'disponivel')

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
