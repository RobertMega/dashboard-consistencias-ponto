# Arquitetura

## Fluxo atual

```text
PDF enviado por ADMIN
  -> diretório temporário privado
  -> automation/parser/pdf_reader.py
  -> RawRecord
  -> automation/parser/normalizer.py
  -> NormalizedRecord
  -> automation/parser/metrics.py + Excel
  -> transação PostgreSQL (ReportRun + DailyRecord)
  -> API Next.js autenticada
  -> dashboard Next.js com paginação
```

O PDF e os artefatos intermediários não são publicados. O JSON local histórico
em `web/public/dashboard-data.json` foi removido; a única imagem pública é o
logo institucional.

## Banco

O schema Prisma está em `web/prisma/schema.prisma` e a migration inicial em
`web/prisma/migrations/202608130001_init/migration.sql`.

`ReportRun.isCurrent` identifica a última execução SUCCESS válida. Os
`DailyRecord` pertencem a um run e têm unicidade por colaborador + data dentro
do run. A base anterior permanece atual enquanto a nova execução estiver
PROCESSING ou FAILED.

## Formato do PDF atual

O arquivo `samples/jornada-exemplo.pdf` possui as seis colunas posicionais de
Pontos. O parser usa PyMuPDF e `page.get_text("words")` para preservar
coordenadas; células vazias não deslocam marcações.

Este PDF não possui horários individuais de Jornada prevista. A fonte oficial
é `Horas previstas`; a expectativa é 2 marcações até 04:00 e 4 acima de 04:00.

## API e segurança

O dashboard consulta `/api/dashboard` com filtros e paginação. A base completa
é calculada no servidor; o navegador recebe apenas a página de registros e os
agregados necessários. `/api/dashboard/employee` fornece o histórico de um
colaborador autenticado.

O acesso usa cookie HttpOnly assinado, com papéis ADMIN e VIEWER. Upload,
histórico e Excel são exclusivos de ADMIN. Não existe cadastro público,
autenticação no Ponto VR, cookies externos ou automação nesta fase.

## Fases futuras

Playwright, login/download automático do Ponto VR, cron, D-1, GitHub Actions e
Vercel só serão tratados após a validação local desta arquitetura.
