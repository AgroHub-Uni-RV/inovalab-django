from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver

from accounts.agrohub.services import SESSION_KEY


@receiver(user_logged_in, dispatch_uid='accounts.persist_agrohub_credentials')
def persist_agrohub_credentials(sender, request, user, **kwargs):
    credential = getattr(request, 'agrohub_login_credentials', None)
    if isinstance(credential, dict) and user.agrohub_id is not None and credential.get('user_id') == user.agrohub_id:
        request.session[SESSION_KEY] = credential
        del request.agrohub_login_credentials
