# InovaLab

Sistema Django para demandas do laboratório, tarefas, agenda, materiais e banners, com frontend básico e API para futuras integrações.

O módulo **Identidade e acesso** está implementado: contas pelo Django Admin, login/logout, página privada e `GET /api/v1/me/`. O responsável autorizou avançar para **Catálogo**, cuja especificação está em revisão. Os demais módulos e seus endpoints seguem como propostas para entregas posteriores.

## Documentação

| Arquivo | Conteúdo |
| --- | --- |
| [01 — Escopo e requisitos](01-InovaLab-Escopo-e-Requisitos.md) | Fontes, requisitos, permissões, perguntas e decisões |
| [02 — Casos de uso](02-InovaLab-Casos-de-Uso.md) | Fluxos internos e integração AgroHub |
| [03 — Cenários e rastreabilidade](03-InovaLab-Cenarios-e-Rastreabilidade.md) | Critérios para testes futuros e vínculo com requisitos |
| [04 — Diretrizes Django](04-InovaLab-Diretrizes-Django.md) | Modelagem, autorização, integridade e concorrência |
| [05 — Revisão e arquitetura](05-InovaLab-Revisao-e-Arquitetura.md) | Telas, diagnóstico, alternativas, API proposta e etapas |
| [06 — Conferência do PDF](06-InovaLab-Conferencia-do-PDF.md) | Comparação por página, cobertura dos requisitos e distinção entre PDF, decisões e propostas |
| [Módulo 1 — Identidade e acesso](docs/modules/01-identidade-e-acesso.md) | Instalação, contas, contrato da API e roteiro para depuração |

Leia as classificações **C** (confirmado pela fonte), **D** (derivado) e **P** (proposta) no arquivo 01. Propostas não são decisões aprovadas. As seis telas e as três páginas de `Referencias/InovaLab - Modelagem.pdf` foram examinadas. A pasta permanece ignorada pelo Git e pode faltar em outro clone.

## Decisões confirmadas em 01/10/2026

- Django com frontend básico e endpoints para futuras integrações.
- Somente administradores aprovam, recusam e reabrem tarefas; o responsável executa e envia para avaliação.
- Cada reserva do MVP tem um único serviço, equipamento ou espaço, sem bloquear automaticamente recursos associados.
- Contas internas cadastradas pelo administrador técnico, com login por usuário e senha.

O primeiro módulo usa Django, templates e Django REST Framework, com política de papéis compartilhada entre interface e API. SQLite atende à execução local desta etapa; banco e concorrência da agenda serão definidos em sua própria entrega.

## Estado do ambiente local

Em 01/10/2026, o módulo foi verificado com Python 3.14.3, Django 6.1.1 e DRF 3.18.1. As dependências diretas estão em `requirements.txt`. A colisão do app local `auth` foi corrigida com `accounts`; a autenticação nativa do Django foi preservada.

Execução em PowerShell (crie `venv` com `python -m venv venv` se necessário):

```powershell
& .\venv\Scripts\python.exe -m pip install -r requirements.txt
& .\venv\Scripts\python.exe manage.py migrate
& .\venv\Scripts\python.exe manage.py createsuperuser
& .\venv\Scripts\python.exe manage.py runserver
```

Abra [o login local](http://127.0.0.1:8000/entrar/), entre com o superusuário e use **Administrar contas** para criar os usuários internos. Não há credenciais padrão. O grupo `Administradores` identifica o papel de negócio e não concede gestão técnica de contas.

Verificação automatizada:

```powershell
& .\venv\Scripts\python.exe manage.py test
& .\venv\Scripts\python.exe manage.py check
& .\venv\Scripts\python.exe manage.py makemigrations --check --dry-run
& .\venv\Scripts\python.exe -m pip check
```

35 testes passaram; checks, migrações e dependências sem pendências. O fluxo foi verificado no Chrome, incluindo layout a 360 px. Consulte o [guia do módulo](docs/modules/01-identidade-e-acesso.md) para variáveis de ambiente, contrato JSON e roteiro manual. `.env` não é carregado automaticamente. Esta entrega é local; hospedagem e produção permanecem por definir.

## Processo

Revisar requisitos e decisões de cada etapa, validar seu desenho, preparar o plano, implementar o fluxo web/API e verificar cenários relevantes. A coleção de skills [Superpowers](https://github.com/obra/superpowers) foi instalada neste ambiente do Codex; não é dependência da aplicação e não acompanha um clone do projeto.

Por decisão do responsável, entregar um módulo por vez e aguardar sua depuração antes do próximo. A primeira entrega segue a [especificação aprovada](docs/superpowers/specs/2026-10-01-identidade-e-acesso-design.md) e o [plano autorizado](docs/superpowers/plans/2026-10-01-identidade-e-acesso.md), executado diretamente com revisão independente ao final. O responsável autorizou iniciar catálogo em 01/10/2026; sua [especificação para revisão](docs/superpowers/specs/2026-10-01-catalogo-design.md) descreve telas simples, endpoints e política de acesso confirmada. Catálogo ainda não foi implementado.

Para as próximas entregas do MVP, usar frontend mais simples, preservando a interface atual de identidade. Executar os testes automatizados do Django e os testes básicos no navegador; o responsável realizará os testes mais profundos posteriormente. Essas orientações estão em [AGENTS.md](AGENTS.md).

Commits importantes seguem o formato em português, por exemplo `feat (docs): adiciona documentação da arquitetura do sistema.`.
