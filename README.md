# Dashboard de Consistências de Ponto

Aplicação para processar o relatório PDF de Jornada, classificar ocorrências,
gerar Excel e exibir um dashboard gerencial privado.

## Estado atual

- Parser Python e regras de negócio validados.
- PostgreSQL privado via Prisma.
- Login com papéis `ADMIN` e `VIEWER`.
- Upload manual de PDF somente para ADMIN.
- Dashboard servido por API autenticada e paginada.
- Histórico de processamentos e download protegido do Excel.
- Playwright, login/download automático do Ponto VR, D-1, GitHub Actions e
  Vercel ainda não foram implementados.

## Desenvolvimento local

Consulte [docs/PRODUCAO_LOCAL.md](docs/PRODUCAO_LOCAL.md) para configurar
PostgreSQL, `.env.local`, migration, ADMIN inicial, login e upload manual.

O fluxo local é:

```text
PDF -> parser/regras Python -> PostgreSQL privado -> API autenticada -> Next.js
```

Não gere dados reais em `web/public`. O logo institucional é o único asset
relacionado ao dashboard que deve permanecer público.

## Testes

```powershell
pytest automation/tests
Set-Location web
npm run test:filters
npm run lint
npm run build
```
