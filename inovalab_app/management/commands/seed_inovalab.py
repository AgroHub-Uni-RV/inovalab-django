from django.core.management.base import BaseCommand
from django.db import transaction
from inovalab_app.catalogo.initial_resources import seed_initial_resources
from inovalab_app.catalogo.initial_services import seed_initial_services
from inovalab_app.models import Equipamento, Servico


class Command(BaseCommand):
    help = 'Carga inicial explícita e idempotente dos serviços e equipamentos do InovaLab.'

    def add_arguments(self, parser):
        parser.add_argument('--database', default='default')

    def handle(self, *args, **options):
        alias = options['database']
        with transaction.atomic(using=alias):
            services = seed_initial_services(Servico, using=alias)
            equipment = seed_initial_resources(Equipamento, using=alias)
        self.stdout.write(self.style.SUCCESS(f'Carga inicial: {services} serviços e {equipment} equipamentos criados.'))
