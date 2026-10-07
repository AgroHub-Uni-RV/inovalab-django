# Correção do contrato de visitas AgroHub

Solicitação autorizada: manter API e aplicar as correções identificadas ao ler `unirv-monolith`, sem alterar esse repositório e sem mudar permissões nesta etapa.

1. Demonstrar RED com HTTP fiel ao serializer real: horários HH:MM, status inicial definido pela sala, erros por campo, antecedência e reservas pendentes bloqueantes.
2. Corrigir payloads novos e novas tentativas conhecidas, sem truncar segundos nem repetir mutação incerta. Manter aprovação local independente do status inicial remoto.
3. Validar localmente precisão/futuro/antecedência e consultar disponibilidade antes da gravação local. Revalidar no envio; a API permanece autoridade final. Mostrar erros específicos no formulário e no resultado durável.
4. Ajustar formulário de visita, testes antigos e documentação. Executar suíte Django, check/drift/diff, navegador com HTTP controlado e revisão independente.
5. Commits convencionais em português; preservar `.env.example` previamente editado pelo usuário. Nenhuma reserva fictícia na API real, nenhum deploy e nenhuma modificação do monolito.

Limites: antecedência remota configurável não é publicada pela API; espelhar localmente em `AGROHUB_MIN_ADVANCE_NOTICE_HOURS` (padrão 2). Consulta de disponibilidade não elimina a concorrência, portanto POST ainda pode rejeitar. Visitas históricas sem vínculo não são exportadas.

Entrega executada: RED reproduziu rejeição de HH:MM:SS; contrato corrigido e testes HTTP passaram. Suíte completa: 523 testes; recorte final de integração/formulário: 55 testes. Navegador verificou criação, conflito, falha/retry e troca de precisão por categoria em desktop/celular. Revisão encontrou e corrigiu a classificação de confirmação HTTP falha após mutação aceita e a preservação da digitação na atualização dos horários. Detalhes no [guia da integração](../../modules/10-visitas-agrohub.md).
