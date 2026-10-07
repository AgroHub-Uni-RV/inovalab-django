from datetime import datetime, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase

from inovalab_app.agenda.models import AgendaEquipamento, BOOKING_MODELS, AgendaServico
from inovalab_app.catalogo.models import Equipamento, Servico


class AgendaFrontendTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_superuser('frontend-admin')
        cls.service = Servico.objects.first()
        cls.equipment = Equipamento.objects.create(nome='Equipamento especial')

    def booking(self, reason='Nome buscável', **kwargs):
        start = datetime.fromisoformat('2026-12-30T10:00:00-03:00')
        return AgendaServico.objects.create(servico=self.service, inicio=start, fim=start+timedelta(hours=1),
            motivo=reason, criado_por=self.admin, **kwargs)

    def test_calendar_sunday_first_and_real_booking_content(self):
        booking = self.booking()
        self.client.force_login(self.admin)
        response = self.client.get('/agenda/?mes=2026-12')
        self.assertEqual(response.context['weeks'][0][0]['date'].weekday(), 6)
        day = next(d for w in response.context['weeks'] for d in w if d['in_month'] and d['date'].day == 30)
        self.assertEqual([b.pk for b in day['bookings']], [booking.pk])

    def test_search_category_counts_and_cancelled_are_filtered(self):
        booking = self.booking()
        self.booking('Cancelado', cancelado_em=booking.inicio)
        AgendaEquipamento.objects.create(equipamento=self.equipment, motivo='Motivo',
            inicio=booking.inicio, fim=booking.fim, criado_por=self.admin)
        self.client.force_login(self.admin)
        response = self.client.get('/agenda/', {'mes': '2026-12', 'q': 'buscável'})
        self.assertEqual([b.pk for b in response.context['object_list']], [booking.pk])
        # Todas as agendas e suas contagens são locais.
        self.assertEqual(response.context['category_counts'], {'servico': 1, 'equipamento': 0, 'visita': 0})
        self.assertNotContains(response, 'Visitas indisponíveis')
        self.assertNotContains(response, 'Cancelado')

    def test_multiday_previews_show_full_interval_in_each_occupied_day(self):
        self.client.force_login(self.admin)
        for end, occurrences in [('2026-10-07T08:00:00-03:00', 3), ('2026-10-06T00:00:00-03:00', 1)]:
            with self.subTest(end=end):
                AgendaServico.objects.all().delete()
                AgendaServico.objects.create(servico=self.service, motivo='Motivo',
                    criado_por=self.admin, inicio=datetime.fromisoformat('2026-10-05T22:00:00-03:00'),
                    fim=datetime.fromisoformat(end))
                response = self.client.get('/agenda/?mes=2026-10')
                label = '05/10 22:00 até ' + ('07/10 08:00' if occurrences == 3 else '06/10 00:00')
                self.assertContains(response, label, count=occurrences)

    def test_midnight_and_pagination_keep_all_calendar_bookings(self):
        start = datetime.fromisoformat('2026-12-31T22:00:00-03:00')
        end = datetime.fromisoformat('2027-01-01T00:00:00-03:00')
        AgendaServico.objects.bulk_create([AgendaServico(servico=self.service, inicio=start, fim=end,
            motivo='Virada', criado_por=self.admin) for _ in range(26)])
        self.client.force_login(self.admin)
        response = self.client.get('/agenda/?mes=2026-12&q=Virada')
        day = next(d for w in response.context['weeks'] for d in w if d['in_month'] and d['date'].day == 31)
        self.assertEqual(day['count'], 26)
        self.assertLessEqual(len(day['bookings']), 3)
        january = self.client.get('/agenda/?mes=2027-01&q=Virada')
        self.assertEqual(january.context['paginator'].count, 0)
        self.assertContains(response, 'q=Virada')
