from django import template

from accounts.policies import is_business_admin

register = template.Library()
register.simple_tag(is_business_admin, name='can_access_agenda')
