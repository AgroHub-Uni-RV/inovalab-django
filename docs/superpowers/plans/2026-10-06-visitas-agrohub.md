# Visitas AgroHub — plano de implementação

**Objetivo:** reservar a sala 1 ao criar visita interna, com vínculo e resultado externo explícitos.
**Arquitetura:** intenção durável por visita, envio síncrono fora da transação local e conciliação sem repetir mutação incerta; manter PATCH/cancelamento no mesmo ID, com lock do vínculo numa transação separada durante a manutenção HTTP.
**Tecnologias:** Django, DRF, cliente HTTP existente e servidor HTTP de testes.
**Especificação:** `docs/superpowers/specs/2026-10-06-visitas-agrohub-design.md`.
**Execução:** inline, no checkout do IDE, preservando a alteração prévia de `.env.example`.

## Foco da revisão

POST incerto não duplica; JWT/identidade do criador não são trocados; referência/ID conferem sala 1 e período; origem não muda após configuração; alterações concorrentes não sobrescrevem intenção enviada; nenhuma nova funcionalidade em equipamentos/serviços.

## 1. Contrato, intenção e envio

Arquivos: `accounts/agrohub/{client,services}.py`, `agenda/agrohub.py`, `agenda/models.py`, migração 0009, `agenda/services.py`, testes `agenda/tests/{agrohub_stub,test_agrohub}.py`.

- [x] Testar HTTP de criação pelo navegador e API, payload da sala 1/dia/horas, usuário Bearer, resposta com/sem ID, refresh, sala inexistente/inativa, validação local sem efeitos externos, falha/resultado incerto e conciliação sem POST duplicado.
- [x] Verificar RED antes da implementação.
- [x] Implementar rotas Agendamentos fixas e GET paginado; `ReservaAgroHub` sem credenciais; intenção dentro da transação local e envio depois dela.
- [x] Verificar GREEN e testes de agenda/contas.

## 2. Manutenção e interface

Arquivos: serviços/view/serializer/URLs/forms/templates da agenda.

- [x] Testar PATCH, cancelamento/rejeição, conversão de categorias, concorrência/versão, identidade errada, permissões/CSRF, origem alterada e visualização/retry de falha após cancelamento.
- [x] Implementar intenção de manutenção no mesmo ID, proteção de operações inconclusivas, tela de resultado e ações autenticadas de nova tentativa/conciliação.
- [x] Verificar GREEN; não retornar sucesso de reserva externa para falhas.

## 3. Entrega

- [x] Rodar suíte completa, `check`, drift e diff; aplicar migração SQLite local.
- [x] Navegador com servidor HTTP de teste: nova visita, resultado externo, manutenção e falha/retry, desktop/celular.
- [x] Revisão independente; corrigir bloqueadores, documentar decisões/limites/testes reais restantes.
- [x] Commits convencionais em português por alterações importantes.

Resultado: 508 testes completos e 28 isolados da integração passaram; migração 0009 local aplicada. Revisão corrigiu claim perdido antes do POST, aprovação local após rejeição, status malformado, recuperação antes da sala e concorrência durante PATCH. A manutenção incerta agora é conciliada somente por GET. [Validação, custo do lock SQLite e depuração real restante](../../modules/10-visitas-agrohub.md).
