from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from inovalab_app.catalogo.models import Servico
from inovalab_app.tarefas.services import save_task


class TaskFixtures:
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_user('gestor')
        cls.admin.groups.add(Group.objects.get(name='Administradores'))
        cls.owner = get_user_model().objects.create_user('ana', is_staff=True)
        cls.other = get_user_model().objects.create_user('bruno', is_staff=True)
        cls.service = Servico.objects.first()
        cls.mine = save_task(actor=cls.admin, data={
            'servico': cls.service, 'responsavel': cls.owner, 'descricao': 'Protótipo privado de Ana',
        })
        cls.theirs = save_task(actor=cls.admin, data={
            'servico': cls.service, 'responsavel': cls.other, 'descricao': 'Demanda privada de Bruno',
        })

    def payload(self, **overrides):
        return {'servico': self.service.pk, 'responsavel': self.owner.pk, 'descricao': 'Nova tarefa', **overrides}
