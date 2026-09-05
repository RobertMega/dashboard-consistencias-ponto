# Automação local do Ponto VR

O worker faz login no link configurado do Ponto VR, solicita o relatório D-1 e
envia as três bases ao dashboard na ordem inconsistência, falta e atraso.

## Configuração

Instale as dependências:

```powershell
python -m pip install -r automation/requirements.txt
python -m playwright install chromium
```

Configure as variáveis no perfil do usuário Windows que executará a tarefa:

```powershell
[Environment]::SetEnvironmentVariable("PONTO_LOGIN_URL", "https://app2.pontomais.com.br/relatorios", "User")
[Environment]::SetEnvironmentVariable("PONTO_REPORT_URL", "https://app2.pontomais.com.br/relatorios", "User")
[Environment]::SetEnvironmentVariable("PONTO_CPF", "<CPF do portal>", "User")
[Environment]::SetEnvironmentVariable("PONTO_PASSWORD", "<senha do portal>", "User")
[Environment]::SetEnvironmentVariable("APP_BASE_URL", "http://localhost:3000", "User")
[Environment]::SetEnvironmentVariable("AUTOMATION_TOKEN", "<mesmo token do web/.env.local>", "User")
[Environment]::SetEnvironmentVariable("PONTO_JOB_TIMEOUT_SECONDS", "600", "User")
```

Os tipos e modelos confirmados são:

- Jornada (espelho ponto) / ROBERT - DASHBOARD: inconsistência, PDF.
- Faltas / ROBERT - PAINEL GERENCIAL: falta, XLS/XLSX.
- Atrasos / ROBERT - DASHBOARD: atraso, XLS/XLSX.

O arquivo `web/.env.local` deve usar o mesmo `AUTOMATION_TOKEN`, além das
variáveis do banco e autenticação.

## Teste e agendamento

Primeiro valide a configuração sem abrir o Ponto VR:

```powershell
python -m automation.run_scheduled --dry-run
```

Depois registre o agendamento:

```powershell
Set-Location C:\caminho\dashboard-consistencias-ponto
.\automation\run_scheduled.ps1
```

O script remove agendamentos antigos de 06:00, 08:00, 14:00 e 15:00 e
registra somente `Dashboard-Consistencias-Ponto-0900`, às 09:00 no horário
local. A tarefa solicita a senha do Windows e permite executar mesmo sem uma
sessão interativa aberta.

Cada base tem timeout independente de 600 segundos por padrão. Uma falha não
impede a tentativa das bases seguintes. Os botões de atualização manual do
dashboard continuam disponíveis.

Nunca registre CPF, senha, token, cookies ou conteúdo dos arquivos em logs,
commits ou mensagens.
