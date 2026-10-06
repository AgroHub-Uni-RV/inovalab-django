from django.contrib.auth.models import AbstractUser
from django.db import models
from uuid import uuid4


def profile_photo_path(instance, filename):
    return f'perfis/{uuid4().hex}.webp'


class User(AbstractUser):
    foto = models.ImageField('foto de perfil', upload_to=profile_photo_path, blank=True)

    class Meta(AbstractUser.Meta):
        verbose_name = 'usuário'
        verbose_name_plural = 'usuários'
