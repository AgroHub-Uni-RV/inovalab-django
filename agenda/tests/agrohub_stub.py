from accounts.tests.agrohub_stub import AccountsStub
from datetime import datetime, timedelta
from urllib.parse import parse_qs, urlsplit
from time import sleep
from django.utils.timezone import now as current_time


class ReservationsStub(AccountsStub):
    def reset(self):
        super().reset()
        self.state.update(reservas=[], sala={'id': 1, 'nome': 'Laboratório InovaLab',
            'slug': 'laboratorio-inovalab', 'site_code': 'inovalab', 'ativa': True,
            'capacidade': None, 'requer_aprovacao': True}, omit_id=False,
            create_error=None, create_uncertain=False, patch_uncertain=False, create_status=None, create_delay=0)

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
            quantity = data.get('quantidade_pessoas')
            capacity = self.state['sala']['capacidade']
            if quantity is not None and (type(quantity) is not int or quantity < 1):
                errors['quantidade_pessoas'] = ['Informe pelo menos uma pessoa.']
            elif capacity is not None and quantity is not None and quantity > capacity:
                errors['quantidade_pessoas'] = ['Quantidade superior à capacidade da sala.']
            if errors:
                handler.reply(400, errors)
                return True
        if path == '/api/v1/agendamentos/reservas/':
            if handler.command == 'GET':
                rows = self.state['reservas']
                if not self.state['profile']['is_staff']:
                    rows = [row for row in rows if row.get('owner_id', 42) == self.state['profile']['id']]
                handler.reply(200, {'results': rows, 'next': None, 'count': len(rows)})
            elif self.state['create_error']:
                handler.reply(self.state['create_error'], {'non_field_errors': ['Horário indisponível.']})
            else:
                timestamp = current_time().isoformat()
                remote = {**data, 'id': len(self.state['reservas'])+101, 'sala': dict(self.state['sala']),
                          'nome_solicitante': 'Ana Silva', 'observacoes': data.get('observacoes', ''),
                          'created_at': timestamp, 'updated_at': timestamp,
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
                if self.state['create_delay']:
                    sleep(self.state['create_delay'])
                    try:
                        handler.reply(201, remote)
                    except OSError:
                        pass  # O cliente pode encerrar após o timeout de uma escrita incerta.
                    return True
                if self.state['create_uncertain']:
                    handler.reply(503, {})
                else:
                    handler.reply(201, data if self.state['omit_id'] else remote)
            return True
        remote_id = int(path.split('/')[5])
        remote = next((row for row in self.state['reservas'] if row['id'] == remote_id), None)
        if remote is not None and not self.state['profile']['is_staff'] and remote.get('owner_id', 42) != self.state['profile']['id']:
            remote = None
        if remote is None:
            handler.reply(404, {})
        elif handler.command == 'PATCH':
            if not self.state['profile']['is_staff'] and ('sala' in data or 'status' in data or remote['status'] != 'pendente'):
                handler.reply(400, {'non_field_errors': ['A alteração não é permitida.']})
                return True
            remote.update(data)
            remote['sala'] = dict(self.state['sala'])
            remote['updated_at'] = current_time().isoformat()
            self.period(remote)
            handler.reply(503, {}) if self.state['patch_uncertain'] else handler.reply(200, remote)
        elif path.endswith('/cancelar/'):
            remote['status'] = 'cancelada'
            remote['updated_at'] = current_time().isoformat()
            handler.reply(200, remote)
        else:
            handler.reply(200, remote)
        return True

    def period(self, remote):
        if 'data' not in remote:
            start, end = datetime.fromisoformat(remote['inicio']), datetime.fromisoformat(remote['fim'])
            remote.update(data=start.date().isoformat(), hora_inicio=start.strftime('%H:%M'), hora_fim=end.strftime('%H:%M'))
        remote['inicio'] = f"{remote['data']}T{remote['hora_inicio']}-03:00"
        remote['fim'] = f"{remote['data']}T{remote['hora_fim']}-03:00"
