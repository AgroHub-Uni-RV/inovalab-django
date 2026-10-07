# Consolidação do InovaLab: plano aprovado

O responsável aprovou a implementação do plano em 07/10/2026. Consolidar o negócio em `inovalab_app`, com pacotes internos shared, catalogo, materiais, tarefas, agenda e conteudo. Accounts e setup permanecem no hospedeiro. Preservar autenticação pela API, URLs, regras, aparência, dados, precisão temporal, arquivos e históricos. Não alterar o monólito.

## Entregas

1. Registrar baseline e fronteira com o hospedeiro por `INOVALAB_HOST_ADAPTER`.
2. Mover código, testes, templates e static para um AppConfig; atualizar relações e middleware sem mudar contratos HTTP.
3. Adotar tabelas existentes com nomes explícitos, inicial unificada, validação prévia, transferência dos ContentTypes mantendo IDs e carga inicial separada.
4. Verificar instalação nova, atualização SQLite/PostgreSQL, usuário alternativo, prefixo HTTP e navegador; documentar operação e fazer commits em português.

## Restrições e revisão

- Banco existente deve primeiro atingir as últimas migrações na versão anterior. Nunca assumir que a existência das tabelas basta para `--fake-initial`.
- Preservar M2M, autores, avaliadores, responsáveis, permissões, grupos e histórico do Admin.
- Contas externas mantêm criação e ações próprias; administradores cancelam somente confirmados.
- Sem mudança de `AUTH_USER_MODEL`, fonte de papéis ou tabela local de identidade nesta entrega.
- Testar isolamento de templates/static, proteção de APIs após renomear módulos e links sob prefixo.
- Publicação e incorporação ao monólito ficam para uma etapa posterior à depuração desta entrega.
