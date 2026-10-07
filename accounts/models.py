from django.contrib.auth.models import AbstractUser
from django.db import models
from uuid import uuid4


def profile_photo_path(instance, filename):
    return f'perfis/{uuid4().hex}.webp'


class User(AbstractUser):
    foto = models.ImageField('foto de perfil', upload_to=profile_photo_path, blank=True)
    agrohub_id = models.PositiveBigIntegerField(null=True, blank=True, unique=True, editable=False)
    agrohub_username = models.CharField(max_length=150, blank=True, editable=False)
    agrohub_roles = models.JSONField(default=list, blank=True, editable=False)
    agrohub_foto_url = models.URLField(max_length=2048, blank=True, editable=False)
    cpf = models.CharField(max_length=14, blank=True)
    telefone = models.CharField(max_length=20, blank=True)

    @property
    def tem_foto(self):
        return bool(self.agrohub_foto_url) if self.agrohub_id is not None else bool(self.foto)

    class Meta(AbstractUser.Meta):
        verbose_name = 'usuário'
        verbose_name_plural = 'usuários'
