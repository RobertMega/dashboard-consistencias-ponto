# Produção na Vercel

## Arquitetura

O projeto usa o Next.js em `web/` e duas Functions Python na raiz:

- `/api/parse`: recebe um PDF pequeno ou uma referência de Blob privado de uma chamada interna autenticada,
  processa em diretório temporário e devolve o payload normalizado e o Excel;
- `/api/export`: recebe somente o contexto autenticado filtrado e devolve um
  Excel gerencial temporário.

O Next.js continua responsável por sessão, autorização ADMIN, persistência e
consulta ao PostgreSQL. O parser Python em `automation/` não é reimplementado
no frontend e suas regras de classificação permanecem a fonte oficial.

## Recursos externos

1. Criar um projeto PostgreSQL Neon pelo Marketplace da Vercel.
2. Criar um projeto Vercel conectado ao repositório correto.
3. Configurar Root Directory na raiz do repositório, pois `api/`,
   `requirements.txt` e `vercel.json` ficam fora de `web/`.
4. Conferir o Preview antes de criar qualquer Production deployment.

## Variáveis

Configurar somente no ambiente apropriado da Vercel, nunca em `vercel.json` ou
no código:

```text
DATABASE_URL
AUTH_SECRET
NEXT_PUBLIC_GOOGLE_CLIENT_ID
GOOGLE_CLIENT_ID
GOOGLE_ALLOWED_EMAILS
GOOGLE_ADMIN_EMAILS
PARSER_SERVICE_TOKEN
PARSER_FUNCTION_URL
CRON_SECRET
UPLOAD_MAX_BYTES
BLOB_READ_WRITE_TOKEN
NEXT_PUBLIC_BLOB_UPLOAD_ENABLED
```

Para aceitar PDFs maiores que o limite de 4,5 MB das Functions, crie um Blob
store **privado** no projeto Vercel. O store fornece `BLOB_READ_WRITE_TOKEN`;
configure também `NEXT_PUBLIC_BLOB_UPLOAD_ENABLED=true` e faça um novo deploy.
O navegador enviará o PDF diretamente ao Blob. O backend passará somente a
referência pequena ao parser Python, que baixará o conteúdo privado, processará
e apagará o arquivo temporário ao terminar. O PDF original não fica público nem
é salvo no PostgreSQL.

## Importação do Excel de atrasos

O arquivo bruto de atrasos permanece fora do Git e do pacote Vercel. Depois de
aplicar a migration em produção, importe a planilha local para o banco privado
usando um arquivo de ambiente temporário ignorado:

```powershell
vercel env pull .env.production.local --environment=production
Set-Location web
node --env-file=../.env.production.local --experimental-strip-types scripts/import-delay.ts
Remove-Item ..\.env.production.local
```

O comando grava somente os registros normalizados e os exports sem CPF. A saída
exibe apenas status, período, totais e faixas; não exibe nomes, CPF ou a URL do
banco.

`PARSER_FUNCTION_URL` só é necessário quando o parser estiver em outro projeto;
na mesma implantação, o código usa `VERCEL_URL`.

Gerar novos valores para produção. Não reutilizar valores locais, não usar
`INITIAL_ADMIN_PASSWORD` permanentemente e não colocar senhas em logs.

## Migrations e ADMIN

Com o banco Neon de produção selecionado na sessão correta:

```powershell
Set-Location web
$env:DATABASE_URL = "<valor fornecido pelo Neon>"
npm.cmd run db:deploy
```

O `GOOGLE_ALLOWED_EMAILS` deve conter os e-mails autorizados e
`GOOGLE_ADMIN_EMAILS` define os administradores, separados por vírgula.
Usuários permitidos são
provisionados como `VIEWER` no primeiro login; a migration permite usuários
sem senha local.

### Público do app Google

Se algum usuário usar uma conta Gmail pessoal, como
`rsmoura70@gmail.com`, configure o app OAuth como **External** no Google Cloud
Console. Apps configurados como **Internal** só aceitam contas pertencentes à
organização do projeto e exibem o erro `403: org_internal` para contas externas.

Durante o desenvolvimento ou enquanto o app estiver em teste, adicione cada
conta autorizada em **Test users** na tela de consentimento OAuth. A conta
também precisa permanecer em `GOOGLE_ALLOWED_EMAILS` na Vercel; as duas listas
são independentes. O modo de teste do Google tem limite de usuários de teste e
as autorizações podem expirar após sete dias. Para uso contínuo, publique o app
como produção conforme as exigências do Google.

### Origem autorizada no Google OAuth

Para o login da implantação publicada em `dashboard-consistencias-ponto.vercel.app`,
abra o OAuth Client ID usado por `NEXT_PUBLIC_GOOGLE_CLIENT_ID` no Google Cloud
Console e adicione esta origem em **Origens JavaScript autorizadas**:

```text
https://dashboard-consistencias-ponto.vercel.app
```

Cadastre somente protocolo e domínio: não inclua `/login`, `/api` ou qualquer
outro caminho. O valor de `GOOGLE_CLIENT_ID` deve ser o mesmo Client ID usado
em `NEXT_PUBLIC_GOOGLE_CLIENT_ID`. Este fluxo usa callback JavaScript, portanto
não precisa de uma URI de redirecionamento autorizada. Para cada domínio de
Preview que também precisar de login, cadastre sua origem separadamente.

## Preview

Instalar a CLI em uma máquina com acesso ao npm e autenticar interativamente:

```powershell
npm install --global vercel
vercel login
vercel link
vercel env add DATABASE_URL preview
vercel env add AUTH_SECRET preview
vercel env add PARSER_SERVICE_TOKEN preview
vercel env add UPLOAD_MAX_BYTES preview
vercel env add BLOB_READ_WRITE_TOKEN preview
vercel env add NEXT_PUBLIC_BLOB_UPLOAD_ENABLED preview
vercel deploy
```

Se a CLI perguntar pelo framework, selecionar Next.js. O `vercel.json` já
define instalação e build usando `web/` e inclui as Functions Python.

Validar no Preview login, sessão anônima, dashboard, filtros, rankings,
drill-down, upload, processamento Python, persistência, histórico, exportação
filtrada por `/api/admin/export` e logout. Também conferir que nomes não aparecem antes do login e que não há
PDF, Excel ou JSON público.

## Production

Somente depois do smoke test do Preview:

```powershell
vercel deploy --prod
```

Repetir o smoke test e guardar a URL gerada pela Vercel no registro de entrega.

## Worker D-1 às 09:00

O download automático é executado na máquina Windows que possui acesso ao
Ponto VR. Configure as variáveis no perfil do usuário dessa máquina, apontando
`APP_BASE_URL` para a URL pública:

```powershell
[Environment]::SetEnvironmentVariable("APP_BASE_URL", "https://dashboard-consistencias-ponto.vercel.app", "User")
[Environment]::SetEnvironmentVariable("AUTOMATION_TOKEN", "<mesmo segredo configurado na Vercel>", "User")
[Environment]::SetEnvironmentVariable("PONTO_CPF", "<CPF do portal>", "User")
[Environment]::SetEnvironmentVariable("PONTO_PASSWORD", "<senha do portal>", "User")
[Environment]::SetEnvironmentVariable("PONTO_JOB_TIMEOUT_SECONDS", "600", "User")
```

Depois instale Playwright e registre as tarefas:

```powershell
python -m pip install -r automation/requirements.txt
python -m playwright install chromium
python -m automation.run_scheduled --dry-run
.\automation\run_scheduled.ps1
```

O script remove as tarefas antigas de 06:00, 08:00, 14:00 e 15:00 e registra
somente `Dashboard-Consistencias-Ponto-0900`, às 09:00 no horário local. O
worker acessa o Ponto VR, baixa D-1 e envia, em sequência, inconsistência em
PDF, falta em XLS/XLSX e atraso em XLS/XLSX. Cada base tem timeout próprio; uma
falha não impede as seguintes. Os botões manuais continuam disponíveis. Os
arquivos temporários são removidos depois do envio.

## Processamento assÃ­ncrono de relatÃ³rios grandes

O upload agora retorna `202` apÃ³s criar um `ReportRun` `QUEUED`. O Workflow
SDK executa o download, parser, normalizaÃ§Ã£o e persistÃªncia fora da requisiÃ§Ã£o
original; o dashboard continua usando apenas `SUCCESS` + `isCurrent`.

Para produÃ§Ã£o, `PARSER_FUNCTION_URL` deve apontar para um serviÃ§o Python
durÃ¡vel (Cloud Run, container gerenciado ou equivalente) que exponha
`/api/parse` e aceite `PARSER_SERVICE_TOKEN`. NÃ£o use a Function Python da
Vercel como parser de relatÃ³rios grandes: seu limite de funÃ§Ã£o nÃ£o deve ser
confundido com a durabilidade do Workflow. A Function permanece no repositÃ³rio
para compatibilidade e testes locais.

Configure tambÃ©m `CRON_SECRET` para que a limpeza agendada remova Blobs de
tentativas falhas/abandonadas apÃ³s 24 horas. Aplique a migration antes de
ativar o novo fluxo:

```powershell
Set-Location web
npm.cmd run db:deploy
```

## Bloqueios conhecidos deste checkout

- O remote Git atual ainda é um placeholder e não deve receber push.
- A máquina atual não possui Vercel CLI autenticada.
- O banco local não deve ser apontado para a Vercel.
- O runtime Python da Vercel precisa ser validado no Preview com o PDF de
  exemplo antes de considerar o processamento de produção aprovado.
