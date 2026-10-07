from accounts.tests.agrohub_stub import AccountsStub
from datetime import datetime, timedelta
from urllib.parse import parse_qs, urlsplit
from django.utils.timezone import now as current_time


class ReservationsStub(AccountsStub):
    def reset(self):
        super().reset()
        self.state.update(reservas=[], sala={'id': 1, 'nome': 'Laboratório InovaLab',
            'slug': 'laboratorio-inovalab', 'site_code': 'inovalab', 'ativa': True,
            'capacidade': None, 'requer_aprovacao': True}, omit_id=False,
            create_error=None, create_uncertain=False, patch_uncertain=False, create_status=None)

    def dispatch_extra(self, handler, data):
        path = handler.path.split('?')[0]
        if path.startswith('/api/v1/agendamentos/') and (self.state['expired']
                or handler.headers.get('Authorization') not in ('Bearer access-1', 'Bearer access-2')):
            handler.reply(401, {})
            return True
        if path == '/api/v1/agendamentos/salas/':
            handler.reply(200, {'results': [self.state['sala']], 'next': None, 'count': 1})
            return True
        if path == '/api/v1/agendamentos/disponibilidade/':
            params = parse_qs(urlsplit(handler.path).query)
            day = params.get('data', [''])[0]
            rows = [row for row in self.state['reservas'] if row['data'] == day
                    and row['status'] in ('pendente', 'confirmada')]
            handler.reply(200, {'sala': self.state['sala']['slug'], 'data': day, 'reservas': [
                {key: row[key] for key in ('id', 'inicio', 'fim', 'status', 'titulo')} for row in rows]})
            return True
        if not path.startswith('/api/v1/agendamentos/reservas/'):
            return False
        if handler.command in ('POST', 'PATCH') and not path.endswith('/cancelar/'):
            errors = {}
            for name in ('hora_inicio', 'hora_fim'):
                if name in data:
                    try:
                        datetime.strptime(data[name], '%H:%M')
                    except (ValueError, TypeError):
                        errors[name] = ['Formato de hora inválido. Use hh:mm.']
            if errors:
                handler.reply(400, errors)
                return True
        if path == '/api/v1/agendamentos/reservas/':
            if handler.command == 'GET':
                handler.reply(200, {'results': self.state['reservas'], 'next': None, 'count': len(self.state['reservas'])})
            elif self.state['create_error']:
                handler.reply(self.state['create_error'], {'non_field_errors': ['Horário indisponível.']})
            else:
                remote = {**data, 'id': len(self.state['reservas'])+101, 'sala': dict(self.state['sala']),
                          'status': self.state['create_status'] or ('pendente' if self.state['sala']['requer_aprovacao'] else 'confirmada')}
                self.period(remote)
                start = datetime.fromisoformat(remote['inicio'])
                if start < current_time()+timedelta(hours=2):
                    handler.reply(400, {'hora_inicio': ['A reserva deve ser feita com pelo menos 2 horas de antecedência.']})
                    return True
                if any(row['status'] in ('pendente', 'confirmada') and row['inicio'] < remote['fim']
                       and row['fim'] > remote['inicio'] for row in self.state['reservas']):
                    handler.reply(400, {'non_field_errors': ['Esta sala já possui uma reserva nesse horário.']})
                    return True
                self.state['reservas'].append(remote)
                if self.state['create_uncertain']:
                    handler.reply(503, {})
                else:
                    handler.reply(201, data if self.state['omit_id'] else remote)
            return True
        remote_id = int(path.split('/')[5])
        remote = next((row for row in self.state['reservas'] if row['id'] == remote_id), None)
        if remote is None:
            handler.reply(404, {})
        elif handler.command == 'PATCH':
            remote.update(data)
            remote['sala'] = dict(self.state['sala'])
            self.period(remote)
            handler.reply(503, {}) if self.state['patch_uncertain'] else handler.reply(200, remote)
        elif path.endswith('/cancelar/'):
            remote['status'] = 'cancelada'
            handler.reply(200, remote)
        else:
            handler.reply(200, remote)
        return True

    def period(self, remote):
        remote['inicio'] = f"{remote['data']}T{remote['hora_inicio']}-03:00"
        remote['fim'] = f"{remote['data']}T{remote['hora_fim']}-03:00"
