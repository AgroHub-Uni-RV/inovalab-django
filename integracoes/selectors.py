from accounts.policies import is_business_admin
from integracoes.models import ClienteIntegracao


def visible_clients(actor):
    queryset = ClienteIntegracao.objects.all()
    return queryset if is_business_admin(actor) else queryset.none()
