from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    class Meta(AbstractUser.Meta):
        verbose_name = 'usuário'
        verbose_name_plural = 'usuários'
