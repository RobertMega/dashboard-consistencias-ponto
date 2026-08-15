# Preparação segura para produção

## Arquitetura

O fluxo desta fase é:

```text
PDF enviado por ADMIN
  -> arquivo temporário fora de public/
  -> parser Python e regras já validadas
  -> transação PostgreSQL (ReportRun + DailyRecord)
  -> API Next.js autenticada
  -> dashboard com paginação
```

O PDF e o XLSX temporários são removidos depois do processamento. O Excel
gerado é armazenado no `ReportRun` e só pode ser baixado por ADMIN através da
API autenticada. A classificação não é reimplementada no frontend.

## Configuração local

Dentro de `web/`, copie `.env.example` para `.env.local` e preencha:

```text
DATABASE_URL="postgresql://usuario:senha@localhost:5432/dashboard_consistencias_ponto?schema=public"
AUTH_SECRET="um segredo aleatório com pelo menos 32 caracteres"
PYTHON_BIN="python"
UPLOAD_MAX_BYTES="26214400"
```

As variáveis `PONTO_*` ficam reservadas para uma fase futura. Nenhuma credencial
do Ponto VR é usada ou salva nesta implementação.

## Banco e ADMIN inicial

```powershell
Set-Location web
npm install
npm run db:generate
npm run db:migrate -- --name init
npm run db:seed-admin
```

Os scripts de Prisma e seed carregam explicitamente o `.env.local` usando o
recurso nativo `node --env-file`; não é necessário exportar as credenciais no
PowerShell. Os valores reais permanecem somente no arquivo local, que não deve
ser versionado nem impresso.

O script usa `upsert`, grava apenas o hash bcrypt da senha e nunca contém uma
senha real no código. Não use a senha de exemplo em ambiente real.

## Execução e teste manual

```powershell
Set-Location web
npm run dev
```

Abra `http://localhost:3000/login`, autentique com o ADMIN criado e entre em
`Atualizar relatório`. Selecione `samples/jornada-exemplo.pdf` e aguarde o
status SUCCESS. O dashboard passa a consultar `/api/dashboard`; nenhum nome,
batida, saldo ou histórico é lido de `web/public`.

VIEWER pode consultar o dashboard, filtros e detalhes, mas recebe 403 nas
rotas de upload, histórico administrativo e download do Excel.

## Idempotência e falhas

Cada execução cria um `ReportRun` PROCESSING. O parser e a geração do Excel
ocorrem antes da transação. A transação grava os `DailyRecord`, desmarca a base
atual e marca o novo run como SUCCESS. Se qualquer etapa falhar, o run fica
FAILED e o último SUCCESS continua com `isCurrent = true`.

Os registros são únicos por `reportRunId + collaborator + date`. Runs antigos
permanecem no histórico para auditoria, sem duplicar a base atual exibida.

## Rotas privadas

- `/login`: autenticação.
- `/api/dashboard`: KPIs, rankings e página de registros filtrados.
- `/api/dashboard/employee`: histórico completo de um colaborador autenticado.
- `/admin`: upload e histórico para ADMIN.
- `/api/admin/report`: processamento manual ADMIN.
- `/api/admin/runs`: histórico ADMIN.
- `/api/admin/excel/:id`: download protegido do Excel.

O cookie de sessão é HttpOnly, SameSite=Lax, Secure em produção e expira em
8 horas. Não há cadastro público, banco de sessão público, cookies do Ponto VR
ou automação de login.
