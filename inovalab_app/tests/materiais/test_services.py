from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Group
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from inovalab_app.materiais.models import Material
from inovalab_app.materiais.selectors import visible_materials
from inovalab_app.materiais.services import MaterialConflict, save_material


DATA = {'nome': 'Filamento', 'categoria': 'Impressão', 'quantidade': '10.000',
        'unidade': 'kg', 'status': 'disponivel', 'fonte': 'Compra do laboratório'}


class MaterialServiceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_user('gestor-material')
        cls.admin.groups.add(Group.objects.get(name='Administradores'))
        cls.user = get_user_model().objects.create_user('leitor-material', is_staff=True)

    def create(self, **changes):
        return save_material(actor=self.admin, data={**DATA, **changes})

    def test_create_normalizes_text_and_preserves_fraction(self):
        material = self.create(nome=' Filamento ', categoria=' Impressão ', unidade=' kg ',
                               fonte=' Compra ', quantidade='0.125')
        material.refresh_from_db()
        self.assertEqual((material.nome, material.categoria, material.unidade, material.fonte),
                         ('Filamento', 'Impressão', 'kg', 'Compra'))
        self.assertEqual(material.quantidade, Decimal('0.125'))
        self.assertEqual(material.versao, 1)

    def test_zero_and_upper_limit_are_valid_without_changing_status(self):
        for value in ('0', '999999999.999'):
            with self.subTest(value=value):
                material = self.create(quantidade=value)
                material.refresh_from_db()
                self.assertEqual(material.quantidade, Decimal(value))
                self.assertEqual(material.status, 'disponivel')

    def test_invalid_quantity_never_persists(self):
        for value in ('-0.001', '0.0001', '1000000000', 'NaN', 'Infinity', True, None):
            with self.subTest(value=value):
                with self.assertRaises(ValidationError):
                    self.create(quantidade=value)
                self.assertEqual(Material.objects.count(), 0)

    def test_float_precision_is_validated_before_model_conversion(self):
        for value in (999999999.9991, 123456789.1234):
            with self.subTest(value=value):
                with self.assertRaises(ValidationError):
                    self.create(quantidade=value)
        self.assertEqual(Material.objects.count(), 0)
        material = self.create()
        with self.assertRaises(ValidationError):
            save_material(actor=self.admin, material_id=material.pk, expected_version=1,
                          data={'nome': 'Não salvar', 'quantidade': 123456789.1234})
        material.refresh_from_db()
        self.assertEqual((material.nome, str(material.quantidade), material.versao), ('Filamento', '10.000', 1))

    def test_required_text_and_status_are_validated(self):
        for field, value in (('nome', ' '), ('categoria', ''), ('unidade', ' '), ('fonte', ''),
                             ('status', 'emprestado'), ('nome', 'a' * 151),
                             ('categoria', 'a' * 101), ('unidade', 'a' * 21), ('fonte', 'a' * 151)):
            with self.subTest(field=field):
                with self.assertRaises(ValidationError):
                    self.create(**{field: value})
        self.assertEqual(Material.objects.count(), 0)

    def test_only_active_business_admins_write(self):
        inactive = get_user_model().objects.create_superuser('inativo-material', is_active=False)
        for actor in (AnonymousUser(), self.user, inactive):
            with self.subTest(actor=actor):
                with self.assertRaises(PermissionDenied):
                    save_material(actor=actor, data=DATA)
        superuser = get_user_model().objects.create_superuser('super-material')
        self.assertEqual(save_material(actor=superuser, data=DATA).nome, 'Filamento')

    def test_only_active_internal_users_consult(self):
        material = self.create(status='indisponivel')
        self.assertEqual(list(visible_materials(self.user)), [material])
        self.assertFalse(visible_materials(AnonymousUser()).exists())
        self.user.is_active = False
        self.assertFalse(visible_materials(self.user).exists())

    def test_correct_quantity_ten_to_eight_with_new_version(self):
        material = self.create()
        updated = save_material(actor=self.admin, material_id=material.pk, expected_version=1,
                                data={'quantidade': '8'})
        material.refresh_from_db()
        self.assertEqual(material.quantidade, Decimal('8.000'))
        self.assertEqual((material.versao, updated.versao), (2, 2))
        self.assertEqual(material.fonte, DATA['fonte'])

    def test_stale_edit_preserves_all_winner_fields(self):
        material = self.create()
        save_material(actor=self.admin, material_id=material.pk, expected_version=1,
                      data={'quantidade': '8', 'unidade': 'g', 'nome': 'Vencedor'})
        with self.assertRaises(MaterialConflict):
            save_material(actor=self.admin, material_id=material.pk, expected_version=1,
                          data={'quantidade': '99', 'unidade': 'kg', 'nome': 'Perdedor'})
        material.refresh_from_db()
        self.assertEqual((material.nome, material.unidade, material.quantidade, material.versao),
                         ('Vencedor', 'g', Decimal('8.000'), 2))

    def test_bad_version_and_unknown_fields_do_not_write(self):
        material = self.create()
        for version in (None, 0, -1, True, '1', 1.0, 9223372036854775807):
            with self.subTest(version=version):
                with self.assertRaises(ValidationError):
                    save_material(actor=self.admin, material_id=material.pk, expected_version=version,
                                  data={'nome': 'Inválido'})
        for field in ('id', 'versao', 'criado_por'):
            with self.subTest(field=field):
                with self.assertRaises(ValidationError):
                    self.create(**{field: 2})
        material.refresh_from_db()
        self.assertEqual((material.nome, material.versao), ('Filamento', 1))

    def test_invalid_edit_preserves_all_fields(self):
        material = self.create()
        with self.assertRaises(ValidationError):
            save_material(actor=self.admin, material_id=material.pk, expected_version=1,
                          data={'nome': 'Não salvar', 'quantidade': '-1'})
        material.refresh_from_db()
        self.assertEqual((material.nome, material.quantidade, material.versao),
                         ('Filamento', Decimal('10.000'), 1))

    def test_database_rejects_negative_quantity_bad_status_and_zero_version(self):
        material = self.create()
        for values in ({'quantidade': -1}, {'status': 'inválido'}, {'versao': 0}):
            with self.subTest(values=values):
                with self.assertRaises(IntegrityError), transaction.atomic():
                    Material.objects.filter(pk=material.pk).update(**values)
