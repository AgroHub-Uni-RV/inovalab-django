from html.parser import HTMLParser

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from inovalab_app.conteudo.models import Banner
from inovalab_app.materiais.models import Material
from inovalab_app.tarefas.services import save_task
from inovalab_app.tests.agenda.helpers import make_booking


class ClearLinkParser(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.links = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == 'a' and 'data-clear-filters' in attributes:
            self.links.append(attributes['href'])


class ClearFiltersTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_superuser('admin-limpar-filtros')
        cls.owner = get_user_model().objects.create_user('responsavel-filtros', is_staff=True)
        cls.other = get_user_model().objects.create_user('outro-filtros', is_staff=True)
        cls.own = make_booking(actor=cls.owner, titulo='Serviço próprio')
        cls.foreign = make_booking(actor=cls.other, titulo='Serviço de outro')
        for booking in (cls.own, cls.foreign):
            save_task(actor=cls.admin, data={'agendamento_servico': booking, 'responsaveis': [cls.owner],
                      'descricao': booking.objeto_nome})
        for status in ('disponivel', 'indisponivel'):
            Material.objects.create(nome=f'Material {status}', categoria='Filtro', quantidade=10,
                                    unidade='g', fonte='Lab', status=status)
        for status in ('ativo', 'inativo'):
            Banner.objects.create(titulo=f'Banner {status}', banner_img='banners/fixture.webp', status=status)

    def setUp(self):
        self.client.force_login(self.admin)

    def clear(self, route, filters, *, suffix=''):
        url = reverse(route)
        response = self.client.get(url, filters)
        self.assertEqual(response.status_code, 200)
        links = ClearLinkParser(response.content.decode()).links
        self.assertEqual(len(links), 1, 'A página precisa oferecer uma única ação de limpar filtros.')
        self.assertEqual(links[0], url + suffix, 'A limpeza não deve conservar filtros nem paginação.')
        clean = self.client.get(links[0])  # Follow the actual fallback link, without JavaScript.
        self.assertEqual(clean.status_code, 200)
        self.assertEqual(clean.context['query'], '')
        self.assertEqual(clean.context['page_obj'].number, 1)
        return clean

    def test_agenda_clear_removes_month_instead_of_restoring_admin_default(self):
        clean = self.clear('agenda:list', {'q': 'não existe', 'mes': '2026-01',
                           'situacao': 'pendente', 'categoria': 'visita', 'page': 1}, suffix='?mes=')
        self.assertEqual((clean.context['month'], clean.context['selected_category'],
                          clean.context['selected_situation']), ('', '', ''))
        self.assertEqual(clean.context['calendar_month'], timezone.localdate().strftime('%Y-%m'))
        self.assertEqual({booking.pk for booking in clean.context['object_list']}, {self.own.pk, self.foreign.pk})

    def test_requests_clear_includes_all_situations_and_months(self):
        clean = self.clear('agenda:requests', {'q': 'não existe', 'mes': '2026-01', 'status': 'pendente'})
        self.assertEqual((clean.context['month'], clean.context['selected_status']), ('', ''))
        self.assertEqual(clean.context['paginator'].count, 2)

    def test_personal_clear_preserves_owner_isolation(self):
        self.client.force_login(self.owner)
        clean = self.clear('agenda:mine', {'q': 'não existe', 'mes': '2026-01',
                                         'situacao': 'pendente', 'categoria': 'visita'})
        self.assertEqual((clean.context['month'], clean.context['selected_category'],
                          clean.context['selected_situation']), ('', '', ''))
        self.assertEqual([booking.pk for booking in clean.context['object_list']], [self.own.pk])
        self.assertNotContains(clean, 'Serviço de outro')

    def test_tasks_clear_removes_status_and_service(self):
        clean = self.clear('tarefas:board', {'q': 'não existe', 'servico': self.own.servico_id, 'status': 'concluido'})
        self.assertEqual((clean.context['selected_service'], clean.context['selected_status']), ('', ''))
        self.assertEqual(clean.context['paginator'].count, 2)

    def test_materials_clear_removes_category_and_status(self):
        clean = self.clear('materiais:list', {'q': 'não existe', 'categoria': 'Filtro', 'status': 'indisponivel'})
        self.assertEqual((clean.context['selected_category'], clean.context['selected_status']), ('', ''))
        self.assertEqual(clean.context['paginator'].count, 2)

    def test_banners_clear_returns_all_statuses(self):
        clean = self.clear('conteudo:list', {'q': 'não existe', 'status': 'inativo'})
        self.assertEqual(clean.context['selected_status'], '')
        self.assertEqual(clean.context['paginator'].count, 2)

    def test_users_clear_returns_all_tabs(self):
        clean = self.clear('accounts:users', {'q': 'não existe', 'tab': 'inativos'})
        self.assertEqual(clean.context['selected_tab'], 'todos')
        self.assertEqual(clean.context['paginator'].count, 3)

    def test_clear_from_real_second_page_returns_first_page_without_query_or_tab(self):
        for index in range(16):
            get_user_model().objects.create_user(f'pagina-usuario-{index}')
        url = reverse('accounts:users')
        response = self.client.get(url, {'q': 'pagina', 'tab': 'ativos', 'page': 2})
        self.assertEqual(response.context['page_obj'].number, 2)
        clean = self.clear('accounts:users', {'q': 'pagina', 'tab': 'ativos', 'page': 2})
        self.assertEqual(clean.context['selected_tab'], 'todos')
        self.assertEqual(clean.context['paginator'].count, 19)
