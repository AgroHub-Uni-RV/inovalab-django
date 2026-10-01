# InovaLab — Diretrizes de modelagem para Django

Versão 0.3 • 01/10/2026. Diretrizes para os módulos futuros; identidade e acesso já implementados conforme o [guia da entrega](docs/modules/01-identidade-e-acesso.md). O primeiro módulo foi verificado com Python 3.14.3, Django 6.1.1 e DRF 3.18.1, usando SQLite local. Banco da agenda e hospedagem serão definidos em suas etapas. A proposta de arquitetura e o diagnóstico histórico estão no arquivo 05.

## 1. Organização sugerida

| App proposto | Responsabilidade |
| --- | --- |
| accounts | Identidade, perfis e autorização |
| catalogo | Serviços, equipamentos e espaços |
| tarefas | Demandas, responsáveis e transições |
| agenda | Agendamentos unificados e regras de disponibilidade |
| materiais | Cadastro de materiais; movimentações apenas se aprovadas |
| conteudo | Banners e publicação |
| integracoes | Contrato e autenticação AgroHub; adaptação ao domínio |

A colisão inicial entre o app local `auth` e `django.contrib.auth` foi corrigida no módulo 1: o scaffold local foi substituído por `accounts`, com usuário baseado em `AbstractUser`, grupo `Administradores` e migrações próprias. `manage.py check` passa. `core` permanece sem funcionalidades de negócio; futuramente deve concentrar elementos compartilhados e a composição do painel.

Separar regras compartilhadas da interface. A API e os formulários devem chamar as mesmas operações de domínio para reservar, editar e excluir. Não implementar uma validação de conflito diferente em cada entrada.

## 2. Entidades e campos

**C:** campo na fonte. **D:** derivação. **P:** adição proposta. Tamanhos, nulabilidade e obrigatoriedade devem ser definidos após Q04/Q09.

| Entidade | Campos da fonte | Complementos e decisões |
| --- | --- | --- |
| Serviço | nome, descricao, status — C | Valores disponível/indisponível; identificador e datas de auditoria — D/P |
| Equipamento | nome, descricao, status — C | Disponível/ocupado/indisponível; distinguir disponibilidade administrativa da ocupação temporal — P |
| Espaço | nome, capacidade_maxima_de_pessoas, status — C | Capacidade positiva — P; participantes por reserva ausentes na fonte |
| Tarefa | servico, descricao, responsavel, status, data_inicio, prazo_final, data_conclusao — C | Título curto opcional — P; não é campo existente na fonte |
| Agendamento | AgroHub: categoria, objeto_agendadado, motivo, data, horario_inicio, horario_fim; Figma: servico, data_hora, requerente — C | Unificação/normalização dos campos — D; origem, id_externo, criado_por, timestamps e versão — P |
| Material | nome, categoria, quantidade, status, fonte — C | Unidade e precisão numérica — P; significado de fonte em aberto |
| Banner | titulo, banner_img WebP, status, local — C | inicio_exibicao, fim_exibicao e texto_alternativo — P |
| Evento de histórico | Não consta | Ator, entidade, instante, operação e mudanças — P |

Usar uma identidade configurável do Django desde o início e referências ao modelo de usuário configurado. Um solicitante AgroHub pode ser representado por identificador externo e dados mínimos aprovados; não presumir ForeignKey obrigatória para usuário interno.

Na conferência direta do PDF, `objeto_agendadado` é a grafia original; normalizar para uma referência íntegra é decisão de implementação, sem exigir esse erro de grafia no novo contrato. `data_hora` do modelo Figma deve ter representação correspondente na reserva unificada. Se houver migração, seu horário final não pode ser inferido de uma duração que a fonte não informa.

## 3. Alvo do agendamento

F3 confirma um único alvo por reserva no MVP. Proposta técnica: três referências opcionais, `servico`, `equipamento` e `espaco`, com restrição de banco garantindo **exatamente uma preenchida**. A categoria deve ser derivada dessa referência ou, se armazenada para integração, validada para corresponder ao alvo.

Evitar apenas `categoria + id_objeto` sem integridade referencial. A alternativa de recurso agendável comum pode ser melhor se houver calendários, capacidades e indisponibilidades compartilhadas; não é necessária antes de esclarecer Q05.

F3 deixa alocações compostas fora do MVP: uma reserva de serviço não bloqueia automaticamente equipamentos, espaços ou operadores. Se isso se tornar necessário, será preciso modelar alocações associadas e verificar todas numa transação. Atendimento simultâneo por serviço permanece pendente em Q05.

## 4. Estados e permissões

Estados internos sugeridos: `demanda`, `criacao`, `avaliacao`, `concluido`. Rótulos visuais: Demanda, Criação, Avaliação e Concluído. `re-criar` não deve ser adicionado.

O filtro de tarefas deve considerar o usuário antes de aplicar busca, paginação ou filtros. Detalhe, exportação futura e alteração também devem validar propriedade. Esconder botões não implementa autorização.

Na operação de usuário comum, aceitar exclusivamente a alteração de status; campos automáticos são definidos pelo servidor. O papel de administrador do negócio não deve depender obrigatoriamente de conceder superusuário do Django.

F3 resolveu a autoridade de Q03: somente administradores aprovam, recusam e reabrem; o responsável executa e envia para avaliação. Aplicar essa autorização tanto na API quanto nos formulários. Destino da reabertura, datas automáticas e demais transições continuam sujeitos à validação do mapa do arquivo 03.

## 5. Datas, conflitos e concorrência

- Escolher armazenamento temporal consistente e fuso institucional; `America/Sao_Paulo` é apenas uma proposta a confirmar.
- Preferir início/fim completos com fuso no domínio da reserva; a interface pode continuar recebendo data e horários separados.
- Definir se reserva atravessa meia-noite, se há preparação entre reservas e se há capacidade paralela por serviço.
- Na política exclusiva proposta, há conflito quando `inicio_existente < fim_novo` e `fim_existente > inicio_novo` para o mesmo recurso.
- Uma transação isolada, sem bloqueio ou restrição adequada, não impede a corrida entre duas consultas que encontram intervalo livre. Bloquear o recurso antes de consultar e gravar, ou utilizar uma restrição de não sobreposição suportada pelo banco escolhido.
- Ao editar, excluir a própria reserva da busca de conflitos; manter proteção de concorrência.
- Não alterar permanentemente um equipamento para “ocupado” só por existir uma reserva futura. Definir cálculo por instante ou separar estado operacional de ocupação.

## 6. Contrato AgroHub a definir

Documentar direção do fluxo, autenticação, versão, identificador externo do pedido, identificação do requerente, categoria, referência ao objeto, motivo, início, fim e fuso. Devolver identificador local e resultado inequívoco.

Propor unicidade de `(origem, id_externo)`. Persistir chave e reserva de forma atômica; repetir pedido idêntico retorna o resultado anterior. Chave repetida com conteúdo diferente deve ser conflito, não uma edição implícita.

Definir se edição/exclusão local precisa de notificação ao AgroHub. Não implementar sincronização bidirecional, webhooks ou aprovação automática como fatos confirmados.

## 7. Integridade e publicação

Proteger serviços, usuários e recursos referenciados contra exclusões em cascata que eliminem registros operacionais. Preferir desativação de cadastros; exclusão de tarefas e reservas continua dependente de Q08, pois é uma ação expressamente solicitada no PDF.

Para materiais, não deduzir estoque disponível apenas de um status cujo vocabulário não foi definido. Se entradas/saídas forem aprovadas, criar movimentos e histórico em vez de somente sobrescrever o saldo.

Para banners, validar o conteúdo real do arquivo. WebP é o formato confirmado; conversão automática não é obrigatória. O estado agendado exige período de exibição, ausente na modelagem original. A seleção por data na leitura pode cumprir a publicação sem exigir um agendador de tarefas.

## 8. Ordem sugerida de implementação

Entregar um módulo por vez e aguardar depuração pelo responsável antes de avançar. Identidade e acesso precedem catálogo; a divisão atualizada está no arquivo 05.

1. Usar a revisão das seis telas F4 e a autoridade confirmada em Q03; validar a primeira etapa da arquitetura e as decisões necessárias a ela. Resolver Q05/Q07 antes da agenda integrada e Q12 antes dos cadastros específicos.
2. Implementar identidade, autorização e cadastros básicos.
3. Implementar tarefas e transições aprovadas, com quadro Kanban conforme referência F4.
4. Implementar agenda unificada e proteção contra conflito.
5. Integrar AgroHub com contrato e cenários de reenvio.
6. Implementar materiais e banners conforme decisões pendentes.
7. Validar cenários do arquivo 03 e metas não funcionais aprovadas.

F3 solicita explicitamente endpoints para futuras integrações, além do AgroHub. Cada módulo deve planejar sua superfície de API junto com a interface, sem pressupor acesso público aos dados. A recomendação é Django com templates e Django REST Framework, compartilhando operações de domínio; bibliotecas e contratos precisam ser verificados por etapa. Frontend separado é alternativa se a experiência futura justificar seu custo.
