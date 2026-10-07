from django.test import TestCase
from django.contrib.auth import get_user_model

from materiais.models import Material
from materiais.tests.test_services import DATA


class MaterialFrontendTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user('leitor', is_staff=True)
        Material.objects.bulk_create([Material(**{**DATA, 'nome': f'Filamento {i:02}', 'categoria': 'Insumos',
                                                'status': 'disponivel' if i else 'indisponivel'}) for i in range(26)])
        Material.objects.create(**{**DATA, 'nome': '<script>Outro</script>', 'categoria': 'Papelaria'})

    def setUp(self):
        self.client.force_login(self.user)

    def test_search_category_and_counts_before_status_tab(self):
        response = self.client.get('/materiais/', {'q': 'Filamento', 'categoria': 'Insumos', 'status': 'indisponivel'})
        self.assertEqual(response.context['stat_counts'], {'total': 26, 'disponivel': 25, 'indisponivel': 1})
        self.assertEqual(response.context['paginator'].count, 1)
        self.assertNotContains(response, '/editar/')
        self.assertContains(response, DATA['fonte'])

    def test_pagination_retains_all_filters_and_invalid_status_is_ignored(self):
        response = self.client.get('/materiais/', {'q': 'Filamento', 'categoria': 'Insumos', 'status': 'disponivel'})
        self.assertEqual(response.context['paginator'].count, 25)
        first = self.client.get('/materiais/', {'q': 'Filamento', 'categoria': 'Insumos', 'status': 'xxx'})
        self.assertEqual(first.context['selected_status'], '')
        self.assertContains(first, 'q=Filamento')
        self.assertContains(first, 'categoria=Insumos')
        self.assertEqual(len(self.client.get('/materiais/', {'q':'Filamento', 'categoria':'Insumos', 'page':2}).context['object_list']), 1)

    def test_free_category_and_search_are_escaped(self):
        response = self.client.get('/materiais/', {'q': '<script>'})
        self.assertEqual(response.context['paginator'].count, 1)
        self.assertNotContains(response, '<script>Outro</script>')
        self.assertContains(response, '&lt;script&gt;Outro&lt;/script&gt;')

