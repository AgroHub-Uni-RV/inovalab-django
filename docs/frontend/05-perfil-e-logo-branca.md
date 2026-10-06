# Perfil editável e logo para fundo azul

A logo original `Referencias/logo_texto_branco.png` foi copiada sem edição para os arquivos estáticos e aplicada no login e na sidebar. A logo de texto azul permanece no cabeçalho público branco.

`/perfil/` permite ao usuário ativo editar o próprio login, nome, sobrenome e foto. Mantém sessão e senha; não permite alterar privilégios nem outra conta. Login precisa ser válido e único. Foram removidos os atalhos da área de perfil, mantendo Salvar perfil e Sair da conta. A navegação geral continua na sidebar.

Fotos aceitam PNG/JPEG/WebP até 5 MB e 16 milhões de pixels. São convertidas para WebP de até 512 px, com nome aleatório e sem metadados de origem. A foto aparece no perfil, cabeçalho e na lista administrativa de usuários. `/usuarios/<id>/foto/` exige sessão e permite consultar somente a própria foto ou, para superusuário ativo, fotos das contas. Não há exposição pública de `/media/`. Substituições preservam arquivos anteriores no armazenamento; limpeza desses arquivos não faz parte desta entrega.

## Validação

```powershell
.\venv\Scripts\python.exe manage.py test --noinput
.\venv\Scripts\python.exe manage.py check
.\venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\venv\Scripts\python.exe manage.py migrate accounts
```

317 testes Django passaram, incluindo edição sem elevação de privilégios, unicidade, preservação da sessão/senha, validação e conversão da imagem, CSRF e acesso às fotos. Configuração sem problemas e migrações sem alterações pendentes no código.

Chrome com banco/mídia de fixtures: login, edição de nome/login, upload, duas fotos carregadas (perfil/cabeçalho), ausência dos atalhos, bloqueio de login duplicado, logout e nova entrada no index. Perfil em 1366/360 px sem transbordamento e sem erros JavaScript. Revisão independente sem problemas críticos/importantes. Capturas: [desktop](screenshots/perfil-edicao-1366.png) e [celular](screenshots/perfil-edicao-360.png); a imagem usada como foto é uma fixture de teste.

Conferir depois com uma foto pessoal, outras proporções, nomes extensos e Firefox/Safari. Ao baixar as alterações em outro ambiente, executar a migração antes de iniciar o servidor. Usar Ctrl+F5 para atualizar os estilos.
