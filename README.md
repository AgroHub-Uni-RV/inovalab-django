# InovaLab

Sistema Django para demandas do laboratório, tarefas, agenda, materiais e banners, com frontend básico e API para futuras integrações.

O repositório está na fase de revisão de requisitos e arquitetura. A aplicação possui apenas o scaffold inicial; rotas de negócio e endpoints descritos são propostas, não funcionalidades disponíveis.

## Documentação

| Arquivo | Conteúdo |
| --- | --- |
| [01 — Escopo e requisitos](01-InovaLab-Escopo-e-Requisitos.md) | Fontes, requisitos, permissões, perguntas e decisões |
| [02 — Casos de uso](02-InovaLab-Casos-de-Uso.md) | Fluxos internos e integração AgroHub |
| [03 — Cenários e rastreabilidade](03-InovaLab-Cenarios-e-Rastreabilidade.md) | Critérios para testes futuros e vínculo com requisitos |
| [04 — Diretrizes Django](04-InovaLab-Diretrizes-Django.md) | Modelagem, autorização, integridade e concorrência |
| [05 — Revisão e arquitetura](05-InovaLab-Revisao-e-Arquitetura.md) | Telas, diagnóstico, alternativas, API proposta e etapas |
| [06 — Conferência do PDF](06-InovaLab-Conferencia-do-PDF.md) | Comparação por página, cobertura dos requisitos e distinção entre PDF, decisões e propostas |

Leia as classificações **C** (confirmado pela fonte), **D** (derivado) e **P** (proposta) no arquivo 01. Propostas não são decisões aprovadas. As seis telas e as três páginas de `Referencias/InovaLab - Modelagem.pdf` foram examinadas. A pasta permanece ignorada pelo Git e pode faltar em outro clone.

## Decisões confirmadas em 01/10/2026

- Django com frontend básico e endpoints para futuras integrações.
- Somente administradores aprovam, recusam e reabrem tarefas; o responsável executa e envia para avaliação.
- Cada reserva do MVP tem um único serviço, equipamento ou espaço, sem bloquear automaticamente recursos associados.

Arquitetura recomendada, ainda em validação: monólito modular Django, templates e Django REST Framework, com operações compartilhadas entre interface e API. Compatibilidade das dependências e banco serão verificados na implementação.

## Estado do ambiente local

Em 01/10/2026, o `venv` usa Python 3.14.3 e Django 6.1.1. Ainda não há manifesto de dependências versionado ou roteiro completo para instalação em outro computador.

Diagnóstico em PowerShell no ambiente existente:

```powershell
& .\venv\Scripts\python.exe -m django --version
& .\venv\Scripts\python.exe manage.py check
```

O segundo comando falha com `Application labels aren't unique, duplicates: auth`: o app local `auth` colide com `django.contrib.auth`. O primeiro módulo corrige essa base e entrega identidade e acesso; catálogo será o seguinte, depois da depuração pelo responsável. Ainda não há instrução de servidor funcional ou deploy.

## Processo

Revisar requisitos e decisões de cada etapa, validar seu desenho, preparar o plano, implementar o fluxo web/API e verificar cenários relevantes. A coleção de skills [Superpowers](https://github.com/obra/superpowers) foi instalada neste ambiente do Codex; não é dependência da aplicação e não acompanha um clone do projeto.

Por decisão do responsável, entregar um módulo por vez e aguardar sua depuração antes do próximo. A primeira entrega será identidade e acesso; sua [especificação aprovada](docs/superpowers/specs/2026-10-01-identidade-e-acesso-design.md) descreve contas pelo Django Admin, login por usuário/senha, logout, página privada e `/api/v1/me/`. O [plano de implementação](docs/superpowers/plans/2026-10-01-identidade-e-acesso.md) aguarda revisão e escolha do método de execução. Este módulo ainda não foi implementado.

Commits importantes seguem o formato em português, por exemplo `feat (docs): adiciona documentação da arquitetura do sistema.`.
