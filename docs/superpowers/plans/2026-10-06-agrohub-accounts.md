# Integração Accounts do AgroHub — plano

**Objetivo:** executar os seis fluxos pela API UniRV, com login exclusivamente remoto.
**Especificação:** `docs/superpowers/specs/2026-10-06-agrohub-accounts-design.md`.
**Arquitetura:** cliente HTTP isolado, backend de autenticação remoto, serviço de vínculo/sessão, revalidação por middleware, formulários e views existentes adaptados. Sessão de banco conserva JWT somente no servidor.
**Tecnologias:** Django, biblioteca HTTP padrão Python, Pillow e templates existentes.

## Foco de revisão

Colisão de identidade local/remota não associa administradores; retorno remoto malformado não autentica; renovação de JWT verifica o mesmo ID; URL/redirect de foto não vaza credenciais; reset/logout não deixa tokens ativos no navegador; API indisponível não permite senha local.

## Entrega no módulo identidade

Arquivos: `accounts/agrohub/{client,services}.py`, `accounts/{backends,middleware,remote_forms,remote_views,photos}.py`, modelos/migração 0004, views/formulários/templates existentes, configuração de backend/base/timeout, templates consumidores de avatar, documentação e testes Accounts.

- [x] Escrever testes reais contra API HTTP em loopback: login/cadastro/erro, colisão com administrador, revalidação/refresh, alteração somente dos campos permitidos, multipart de foto, reset e confirmação, falhas de rede e CSRF.
- [x] Rodar `venv/Scripts/python.exe manage.py test accounts.tests.test_agrohub --noinput` e verificar RED antes de implementar.
- [x] Implementar cliente de rotas fixas com limites/timeout/erros e sem redirects; autenticação, vínculo e middleware sem copiar roles.
- [x] Implementar os formulários e telas dos seis fluxos, proxy de fotos e proteção da recuperação.
- [x] Adaptar os testes anteriores do requisito de senha local substituído, mantendo cobertura de autorização/layout/CSRF.
- [x] Executar suíte completa, check, drift e navegador com API local controlada, desktop/celular; aplicar migração local aditiva.
- [x] Revisão independente, correções verificadas; documentar comandos, resultados e testes reais restantes.
- [x] Registrar commits convencionais em português: `5ddc4cc` (integração), `ca5f519` (confirmações visuais) e documentação nesta entrega.

## Evidências

- Testes iniciais reproduziram autenticação local ainda ativa e ausência de cadastro/recuperação. Depois, 27 testes de integração Accounts e a suíte final de 472 testes passaram.
- `manage.py check` sem problemas; `makemigrations --check --dry-run` sem drift; `git diff --check` sem erros. Aplicada `accounts.0004_identidade_agrohub` no SQLite local.
- Navegador com API HTTP controlada: seis fluxos, logout, avatares, URL final limpa/sem token no HTML; perfil em 1200 px com sidebar expandida e em 360 px, sem transbordamento externo.
- Revisão independente identificou perda de JWT ao trocar contas no admin, token de recuperação no next de sessão expirada, leitura HTTP interrompida e URL malformada de foto. Corrigidos e revisados novamente sem bloqueadores; regressões dos dois primeiros e da URL malformada falharam antes da correção e passaram depois.
- POST de recuperação em HTTP no navegador demonstrou Origin null com no-referrer no formulário. Captura da URL continua no-referrer; página limpa usa same-origin, e a confirmação passou com CSRF.
- Validação real de conta, e-mail/link e mídia externa permanece no roteiro do [guia da entrega](../../modules/09-agrohub-accounts.md). Nenhuma mutação remota, implantação ou migração de produção foi realizada.
