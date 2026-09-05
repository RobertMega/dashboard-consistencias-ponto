# Dashboard de Consistências de Ponto

Aplicação para processar o relatório PDF de Jornada, classificar ocorrências,
gerar as bases de inconsistências, faltas e atrasos e exibir um dashboard
gerencial privado.

## Fluxo automático

O worker Windows acessa o link configurado do Ponto VR com `PONTO_CPF` e
`PONTO_PASSWORD`, seleciona o período D-1 e baixa, nesta ordem, os relatórios:

| Base | Tipo | Modelo | Formato | Endpoint |
|---|---|---|---|---|
| Inconsistência | Jornada (espelho ponto) | ROBERT - DASHBOARD | PDF | `/api/automation/report` |
| Falta | Faltas | ROBERT - PAINEL GERENCIAL | XLS/XLSX | `/api/automation/absence` |
| Atraso | Atrasos | ROBERT - DASHBOARD | XLS/XLSX | `/api/automation/delay` |

As três bases são processadas sequencialmente às 09:00, com timeout individual
de 600 segundos por padrão. Se uma falhar, as seguintes continuam; o resumo
registra o resultado de cada base. Os botões de atualização manual permanecem
disponíveis no dashboard.

## Desenvolvimento local

Consulte [docs/PRODUCAO_LOCAL.md](docs/PRODUCAO_LOCAL.md) para configurar
PostgreSQL, `.env.local`, migration, Google, login e upload manual. O fluxo é:

```text
Ponto VR -> worker D-1 -> APIs protegidas -> parser/regras -> PostgreSQL -> dashboard
```

Instale as dependências do worker e o navegador:

```powershell
python -m pip install -r automation/requirements.txt
python -m playwright install chromium
```

Depois configure as variáveis do usuário Windows usando
[docs/AUTOMACAO_LOCAL.md](docs/AUTOMACAO_LOCAL.md) e valide sem acessar o
portal:

```powershell
python -m automation.run_scheduled --dry-run
```

Para registrar o único agendamento diário às 09:00:

```powershell
.\automation\run_scheduled.ps1
```

Nunca versionar CPF, senha, tokens, cookies, PDFs reais ou planilhas reais.
