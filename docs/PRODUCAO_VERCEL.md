# Produção na Vercel

## Arquitetura

O projeto usa o Next.js em `web/` e duas Functions Python na raiz:

- `/api/parse`: recebe um PDF apenas de uma chamada interna autenticada,
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
PARSER_SERVICE_TOKEN
UPLOAD_MAX_BYTES
```

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
npm.cmd run db:seed-admin
```

O seed deve receber credenciais novas por variáveis temporárias ou pelo
procedimento seguro adotado pela equipe. Depois de criar o ADMIN, remover
qualquer variável de seed e não registrar a senha no terminal compartilhado.

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

## Bloqueios conhecidos deste checkout

- O remote Git atual ainda é um placeholder e não deve receber push.
- A máquina atual não possui Vercel CLI autenticada.
- O banco local não deve ser apontado para a Vercel.
- O runtime Python da Vercel precisa ser validado no Preview com o PDF de
  exemplo antes de considerar o processamento de produção aprovado.
