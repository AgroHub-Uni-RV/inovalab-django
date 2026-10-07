from django import template

from inovalab_app.agenda.policies import can_access_agenda

register = template.Library()
register.simple_tag(can_access_agenda, name='can_access_agenda')
