# Agendamento de visitas — plano de implementação

> Atualização de 07/10/2026: o módulo de integradores, sua API e seus recibos foram retirados. As referências a esse módulo nesta entrega registram decisões anteriores e não descrevem funções disponíveis. As conexões de Accounts, eventos e contato permanecem.

> Execução nesta sessão pela skill executing-plans, com testes antes da implementação e revisão independente ao final.

**Objetivo:** substituir espaços por visitas nas entradas de agendamento e atualizar os requisitos.
**Arquitetura:** indicador `visita` em Agendamento, com alvo nulo; FK de espaço preservada exclusivamente para legado. Trava transacional única para visitas mantém a exclusividade provisória e a proteção de concorrência.
**Tecnologias:** Django, DRF, SQLite/PostgreSQL e templates existentes.
**Especificação:** `docs/superpowers/specs/2026-10-06-agendamento-visitas-design.md`.

## Restrições

Preservar dados antigos, autoria automática, permissões, cancelamento lógico, UI compartilhada e alterações locais. Apenas módulo agenda nesta entrega.

## Foco de revisão

Troca de categoria limpa dados incompatíveis; PATCH exige campos necessários ao mudar de alvo; visitas respeitam data local; legado permanece consultável/cancelável; reenvio externo anterior não cria duplicatas.

## Entrega única

Arquivos: `agenda/{models,services,forms,serializers,selectors,views}.py`, migração 0008, templates da agenda, CSS, adaptador em `integracoes`, testes e documentação de requisitos/contratos.
Interface: `save_booking(actor, data, booking_id=None, expected_version=None)` aceita categoria visita sem objeto/motivo/observações; propriedades de leitura continuam compatíveis com recursos e legado.

- [x] Escrever testes de criação de visita sem objeto, rejeição de espaço, campos da visita, conflitos/limites, aprovação/cancelamento, legado e integração.
- [x] Executar `venv/Scripts/python.exe manage.py test agenda.tests.test_visits --noinput` e confirmar falhas pelo comportamento ausente.
- [x] Implementar modelo/migração e validações compartilhadas; ajustar formulário/API/filtros/templates/integração.
- [x] Atualizar testes dos requisitos substituídos, preservando cobertura de disponibilidade, autorização, auditoria e integridade.
- [x] Atualizar RF12/RF15/RF16/RN04/Q05, casos/cenários/arquitetura e contratos. Distinguir correção atual das fontes históricas.
- [x] Executar todos os testes Django, check e makemigrations --check; verificar formulário, criação, conflito, filtros e navegação no navegador.
- [x] Revisar alterações e fazer commits convencionais em português; informar resultado e políticas provisórias.

## Registro da execução

Entrega implementada e verificada: 445/445 testes, check e drift sem pendências; migração local 0008 aplicada. RED inicial demonstrou espaço ainda reservável e visita sem suporte; GREEN confirmou novo contrato. Teste concorrente revelou leitura antes da trava de visitas no SQLite, corrigida para escrita antes da leitura. Revisão independente identificou ação Editar indevida no legado, corrigida RED→GREEN. Teste de migração 0007→0008 preservou espaço, textos, versão, datas e evento.

Decisões provisórias: uma visita confirmada por intervalo e preservação de espaços como legado sem edição/aprovação. Se a política pretendida for diferente, a primeira exige ajustar exclusividade; a segunda preserva os dados para tratamento posterior. Nenhuma publicação ou migração de produção nesta entrega. Depuração do responsável antecede avanço para outro módulo.
