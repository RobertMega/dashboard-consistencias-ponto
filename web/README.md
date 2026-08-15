# Dashboard web

O dashboard agora usa PostgreSQL privado e API autenticada. Não gere nem
publique `dashboard-data.json` para executar esta versão.

Consulte [`docs/PRODUCAO_LOCAL.md`](../docs/PRODUCAO_LOCAL.md) para configurar
`.env.local`, PostgreSQL, Prisma, ADMIN, login e upload manual.

Com o banco configurado:

```powershell
npm install
npm run db:generate
npm run db:migrate
npm run db:seed-admin
npm run dev
```

O logo em `public/` é institucional e não contém dados pessoais. Todos os
dados do relatório são servidos por rotas privadas.
