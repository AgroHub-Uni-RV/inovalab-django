from tempfile import TemporaryDirectory
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from inovalab_app.agenda.models import AgendaServico
from inovalab_app.agenda.services import save_booking
from inovalab_app.tests.agenda.helpers import service_data
from inovalab_app.tests.conteudo.helpers import image_upload
from inovalab_app.tests.http import close_response


class BookingServiceDetailsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_user('criador', first_name='Nicole', last_name='Dias')
        cls.admin.groups.add(Group.objects.get(name='Administradores'))
        cls.editor = get_user_model().objects.create_user('editor')
        cls.editor.groups.add(Group.objects.get(name='Administradores'))
        cls.reader = get_user_model().objects.create_user('leitor', is_staff=True)

    def setUp(self):
        self.client.force_login(self.admin)

    def create(self):
        return save_booking(actor=self.admin, data=service_data())

    def test_resources_cannot_be_assigned_to_a_service_request(self):
        for name in ('equipamentos', 'material_proprio', 'material_gasto', 'material_gasto_gramas'):
            with self.subTest(name=name), self.assertRaises(ValidationError):
                save_booking(actor=self.admin, data={**service_data(), name: 1})
        self.assertFalse(AgendaServico.objects.exists())

    def test_detail_header_shows_creator_name_instead_of_requester(self):
        booking = self.create()
        response = self.client.get(f'/agenda/{booking.categoria}/{booking.pk}/')
        self.assertEqual(response.context['creator_name'], 'Nicole Dias')
        self.assertContains(response, 'aria-label="Criado por Nicole Dias"')
        self.assertNotContains(response, '<dt>Requerente</dt>')
        self.assertContains(response, 'class="booking-category">Serviços')
        self.assertNotContains(response, 'aria-label="Criado por Requerente distinto"')

    def test_service_status_is_visible_once_in_header_and_pending_notice_is_preserved(self):
        booking = self.create()
        for status, label in (('confirmado', 'Confirmado'), ('pendente', 'Pendente'),
                              ('rejeitado', 'Rejeitado')):
            with self.subTest(status=status):
                AgendaServico.objects.filter(pk=booking.pk).update(situacao=status)
                response = self.client.get(f'/agenda/servico/{booking.pk}/')
                self.assertEqual(response.status_code, 200)
                header, content = response.content.decode().split('<div class="sheet-layout">', 1)
                self.assertIn(f'booking-status {status}', header)
                self.assertIn(label, header)
                self.assertNotIn('booking-status', content)
                if status == 'pendente':
                    self.assertIn('Aguardando confirmação administrativa no InovaLab', content)
                else:
                    self.assertNotIn('Aguardando confirmação administrativa no InovaLab', content)

    def test_external_creator_falls_back_to_creation_history_name(self):
        booking = self.create()
        AgendaServico.objects.filter(pk=booking.pk).update(criado_por=None)
        booking.eventos.filter(acao='criar').update(ator_nome='Integração: AgroHub')
        response = self.client.get(f'/agenda/{booking.categoria}/{booking.pk}/')
        self.assertEqual(response.context['creator_name'], 'Integração: AgroHub')
        self.assertNotContains(response, '/criador/foto/')

    def test_creator_photo_is_available_only_to_authorized_agenda_users(self):
        with TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            self.admin.foto.save('criador.webp', image_upload(), save=True)
            booking = self.create()
            self.client.force_login(self.editor)
            url = f'/agenda/{booking.categoria}/{booking.pk}/criador/foto/'
            self.assertContains(self.client.get(f'/agenda/{booking.categoria}/{booking.pk}/'), url)
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response['Content-Type'], 'image/webp')
            self.assertIn('no-store', response['Cache-Control'])
            close_response(response)
            self.assertEqual(self.client.get(f'/usuarios/{self.admin.pk}/foto/').status_code, 403)
            self.client.force_login(self.reader)
            self.assertEqual(self.client.get(url).status_code, 404)
            self.client.logout()
            self.assertEqual(self.client.get(url).status_code, 302)
