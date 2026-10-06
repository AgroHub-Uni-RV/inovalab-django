# Seleção de espaços e material consumido — 06/10/2026

Na criação e edição de agendamentos de Espaço, o campo de objeto foi substituído por cartões com seleção única, seguindo a imagem fornecida. A ordem dos espaços iniciais é Secretaria, Sala 01, Sala 02, Área de convivência, Sala 03, Sala 04, Espaço de coworking, Laboratório maker e Laboratório de robótica. Espaços adicionados posteriormente aparecem depois dos iniciais, por nome.

Os cartões usam os nomes, capacidades e restrições atuais do cadastro. Secretaria tem fundo verde; os laboratórios exclusivos de administradores têm fundo azul; os demais têm fundo branco, capacidade em pessoas e ícone de mobiliário. O cadeado indica a restrição administrativa, sem impedir a seleção por administradores autorizados. As permissões e os conflitos de horários existentes continuam sendo aplicados no servidor.

A seleção usa radios nativos, com agrupamento por fieldset e legend, rótulos acessíveis, foco e indicação visual da opção selecionada. Clique no cartão ou use as setas do teclado. A faixa permite rolagem horizontal em telas pequenas, sem ampliar a largura da página. A seleção não salva o agendamento: é necessário usar Salvar agendamento.

## Material utilizado no serviço

Quando Tem material próprio? é Não, aparecem Material utilizado (select de materiais cadastrados) e Material gasto (g). Ambos são obrigatórios no formulário. Sim oculta e desabilita os dois campos; ao salvar, suas informações são limpas. Equipamentos continuam opcionais.

O select oferece materiais disponíveis e, na edição, conserva o material já vinculado mesmo se tiver sido desativado. Um material indisponível não pode ser acrescentado nem usado ao mudar o período da reserva. Editar somente dados descritivos de uma reserva anterior e cancelar continuam permitidos.

O material é vinculado ao agendamento por FK protegida e aparece no detalhe do serviço. A quantidade continua sendo informada em gramas, independentemente da unidade de cadastro do estoque. Esta entrega identifica o consumo; não converte unidades nem altera o saldo do estoque.

A API interna aceita e devolve `material_gasto` como ID de material, além de `material_gasto_gramas`. O campo é opcional na API para preservar registros e consumidores anteriores. Registros antigos sem identificação do material mostram Não informado; ao editar pelo formulário com material do laboratório, é necessário escolher o material. IDs inválidos e associações fora de serviço com material do laboratório são rejeitados. A restrição também existe no banco. O vínculo integra o histórico, a gravação transacional e o controle de versão. A API externa mantém seu contrato anterior.

## Validação

```powershell
& .\venv\Scripts\python.exe manage.py migrate
& .\venv\Scripts\python.exe manage.py test --noinput
& .\venv\Scripts\python.exe manage.py test agenda.tests.test_spaces_and_material agenda.tests.test_service_details --noinput
& .\venv\Scripts\python.exe manage.py check
& .\venv\Scripts\python.exe manage.py makemigrations --check --dry-run
node --check core/static/core/auto-apply.js
git diff --check
```

Suíte completa: 355 testes aprovados. Os 10 testes novos cobrem cartões, ordem, seleção e validação, material obrigatório no formulário, preservação na edição/atualização, disponibilidade, API, histórico, troca de categoria, cancelamento, versão e invariantes no banco. Os 26 testes específicos passaram novamente após os ajustes finais de apresentação. Verificações Django, migrações e sintaxe JavaScript sem pendências. Migração da agenda `0004` aplicada no banco local; executar migrate nos demais ambientes.

Chrome com banco de teste em memória: seleção por clique e teclado, criação de reserva de Sala 02, troca automática para Serviço, campos de material condicionais, preservação dos valores ao alternar Sim/Não e criação de serviço sem máquinas com material selecionado e 15,250 g. Detalhes exibiram o espaço/material correto. Conferência visual em desktop com sidebar expandida e celular de 360 px, sem rolagem lateral da página. Nenhum erro JavaScript registrado. Dados de verificação ficaram somente no banco em memória.

Depuração restante pelo responsável: conferir nomes e capacidades reais, materiais usados pela equipe, textos longos e dispositivos/navegadores de uso diário. Movimentação de estoque permanece fora desta entrega.
