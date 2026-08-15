# Modelo de dados

O registro analítico é identificado por `employee_name + work_date`. A
matrícula não faz parte da saída pública.

Valores de duração são convertidos para minutos inteiros. O valor textual
original do PDF é preservado para marcações e observação; `original_balance`
representa a coluna `Saldo` do relatório, enquanto
`calculated_daily_balance_minutes` é calculado como `Horas totais - Horas
previstas` quando os dois campos existem.

`additional_night_minutes` representa a coluna adicional noturno do relatório e
é mantido separado das horas totais.

`parse_warnings` e `source_page` permitem auditar registros com baixa
confiança sem inventar valores ausentes.
