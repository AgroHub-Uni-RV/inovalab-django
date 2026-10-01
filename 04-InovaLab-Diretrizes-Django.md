# InovaLab — Diretrizes de modelagem para Django

Versão 0.1 • 01/10/2026. Recomendações técnicas, não código implementado. Django é a única escolha tecnológica confirmada. A versão do framework, banco, hospedagem e bibliotecas devem ser definidas na implementação.

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

Separar regras compartilhadas da interface. A API e os formulários devem chamar as mesmas operações de domínio para reservar, editar e excluir. Não implementar uma validação de conflito diferente em cada entrada.

## 2. Entidades e campos

**C:** campo na fonte. **D:** derivação. **P:** adição proposta. Tamanhos, nulabilidade e obrigatoriedade devem ser definidos após Q04/Q09.

| Entidade | Campos da fonte | Complementos e decisões |
| --- | --- | --- |
| Serviço | nome, descricao, status — C | Valores disponível/indisponível; identificador e datas de auditoria — D/P |
| Equipamento | nome, descricao, status — C | Disponível/ocupado/indisponível; distinguir disponibilidade administrativa da ocupação temporal — P |
| Espaço | nome, capacidade_maxima_de_pessoas, status — C | Capacidade positiva; participantes por reserva ausentes na fonte |
| Tarefa | servico, descricao, responsavel, status, data_inicio, prazo_final, data_conclusao — C | Título curto opcional — P; não é campo existente na fonte |
| Agendamento | categoria, objeto, motivo, data, horario_inicio, horario_fim; requerente no modelo Figma — C | Unificação dos campos — D; origem, id_externo, criado_por, timestamps e versão — P |
| Material | nome, categoria, quantidade, status, fonte — C | Unidade e precisão numérica — P; significado de fonte em aberto |
| Banner | titulo, banner_img WebP, status, local — C | inicio_exibicao, fim_exibicao e texto_alternativo — P |
| Evento de histórico | Não consta | Ator, entidade, instante, operação e mudanças — P |

Usar uma identidade configurável do Django desde o início e referências ao modelo de usuário configurado. Um solicitante AgroHub pode ser representado por identificador externo e dados mínimos aprovados; não presumir ForeignKey obrigatória para usuário interno.

## 3. Alvo do agendamento

Proposta inicial simples: três referências opcionais, `servico`, `equipamento` e `espaco`, com restrição de banco garantindo **exatamente uma preenchida**. A categoria deve ser derivada dessa referência ou, se armazenada para integração, validada para corresponder ao alvo.

Evitar apenas `categoria + id_objeto` sem integridade referencial. A alternativa de recurso agendável comum pode ser melhor se houver calendários, capacidades e indisponibilidades compartilhadas; não é necessária antes de esclarecer Q05.

Um serviço pode consumir simultaneamente espaço, equipamento e operador. O PDF não modela essa associação. Se isso for necessário, uma única referência por reserva não basta: será preciso modelar alocações associadas e verificar todas numa transação.

## 4. Estados e permissões

Estados internos sugeridos: `demanda`, `criacao`, `avaliacao`, `concluido`. Rótulos visuais: Demanda, Criação, Avaliação e Concluído. `re-criar` não deve ser adicionado.

O filtro de tarefas deve considerar o usuário antes de aplicar busca, paginação ou filtros. Detalhe, exportação futura e alteração também devem validar propriedade. Esconder botões não implementa autorização.

Na operação de usuário comum, aceitar exclusivamente a alteração de status; campos automáticos são definidos pelo servidor. O papel de administrador do negócio não deve depender obrigatoriamente de conceder superusuário do Django.

Q03 é bloqueador para restringir conclusão a administradores: a fonte diz que usuário altera status, mas não especifica quais transições. O fluxo proposto precisa ser aprovado antes de virar uma restrição.

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

1. Incorporar as seis imagens e resolver Q03, Q05, Q07 e permissões de Q12.
2. Implementar identidade, autorização e cadastros básicos.
3. Implementar tarefas e transições aprovadas, com quadro Kanban se confirmado.
4. Implementar agenda unificada e proteção contra conflito.
5. Integrar AgroHub com contrato e cenários de reenvio.
6. Implementar materiais e banners conforme decisões pendentes.
7. Validar cenários do arquivo 03 e metas não funcionais aprovadas.

Não é necessário criar API para toda a aplicação só porque existe uma integração externa. A escolha entre templates Django e frontend separado deve seguir a experiência desejada e o custo de manutenção.
