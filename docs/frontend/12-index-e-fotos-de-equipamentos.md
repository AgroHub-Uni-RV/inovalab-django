# Index pessoal e fotos dos equipamentos

Entrega de 06/10/2026, autorizada para implementação direta e push na main.

- O index do usuário comum apresenta o mesmo card de agendamentos do administrador, com as abas existentes e somente as reservas confirmadas do próprio usuário. Pedidos pendentes e rejeitados continuam disponíveis na página de agendamentos.
- Equipamento possui `foto` opcional, editável pelos administradores no catálogo e pela API. É possível enviar, substituir e limpar a imagem.
- A migração `catalogo.0005_equipamento_foto` associa as seis fotos de `Referencias/equipamentos` às máquinas iniciais. Os arquivos distribuídos ficam em `catalogo/static/catalogo/equipamentos`; novas imagens ficam no armazenamento de mídia.
- A criação de agendamento de equipamento usa cartões com foto, nome e descrição, seleção única e navegação por teclado. Serviços usam os mesmos cartões para a seleção opcional de várias máquinas. Equipamentos sem imagem mostram um espaço reservado.
- As fotos também aparecem no detalhe do equipamento e de seu agendamento. A leitura exige autenticação e um arquivo associado a um equipamento existente.

## Verificação

Comandos executados:

```powershell
.\venv\Scripts\python.exe manage.py migrate
.\venv\Scripts\python.exe manage.py test
.\venv\Scripts\python.exe manage.py check
.\venv\Scripts\python.exe manage.py makemigrations --check --dry-run
git diff --check
```

Suíte completa: 394 testes aprovados. Verificação Django sem problemas e sem migrações pendentes de geração. A migração foi aplicada no ambiente local.

Navegador verificado com contas temporárias em cópia isolada do banco: card pessoal mostra a reserva própria e oculta a de outro usuário; seis imagens carregadas, seleção única de equipamento, seleção múltipla opcional em serviço, manutenção do formulário ao trocar categoria sem recarregar o documento, menu expandido e recolhido. Desktop de 1264 px e celular de 390 px sem rolagem horizontal; cartões em quatro e duas colunas, respectivamente. Nenhum erro JavaScript observado.

Os testes automatizados cobrem upload, substituição, limpeza, imagem inválida, acesso comum versus administrador, API, imagem inicial, espaço reservado, seleção mantida após erro e foto no detalhe do agendamento.

Para a depuração do responsável: validar fotos próprias de outros tamanhos, navegação por teclado em seus navegadores habituais e o fluxo real de solicitação/aprovação com equipamentos. Outros ambientes devem executar `manage.py migrate` e o procedimento habitual de publicação dos arquivos estáticos.
