from accounts.policies import is_business_admin
from agenda.models import Agendamento


def visible_bookings(actor):
    queryset = Agendamento.objects.filter(cancelado_em__isnull=True).select_related(
        'servico', 'equipamento', 'espaco', 'criado_por',
    )
    return queryset if is_business_admin(actor) else queryset.none()
