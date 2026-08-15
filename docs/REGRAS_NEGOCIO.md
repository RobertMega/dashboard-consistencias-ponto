# Regras de negócio

## Fonte da carga planejada

O PDF atual não possui horários individuais da Jornada prevista. A única fonte
oficial da carga planejada é `Horas previstas`.

`expected_markings_from_planned_hours()` centraliza a regra configurável:

- carga maior que `00:00` e até `04:00`: 2 marcações esperadas;
- carga maior que `04:00`: 4 marcações esperadas;
- carga igual a `00:00` ou inválida: sem expectativa.

As marcações realizadas vêm exclusivamente das seis colunas de Pontos. Células
vazias não contam.

## Classificações

- `PONTO_A_JUSTIFICAR`: horas previstas maiores que zero e zero marcações.
  Severidade `CRITICA`. O sistema sinaliza a pendência sem concluir que se
  trata de falta.
- `MARCACAO_IMPAR`: horas previstas maiores que zero e quantidade realizada
  ímpar. Tem precedência sobre comparação de quantidade. Severidade `CRITICA`.
- `MARCACOES_INCOMPLETAS`: horas previstas maiores que zero, quantidade
  realizada par e positiva, mas menor que a expectativa. Severidade `ATENCAO`.
- `MAIS_QUE_PREVISTO`: quantidade realizada maior que a expectativa. A regra
  usa quantidade de marcações, nunca horas trabalhadas. Severidade `ATENCAO`.
- `PONTO_SEM_JORNADA`: horas previstas iguais a `00:00` e existe marcação.
  Severidade `ATENCAO`.
- `SEM_JORNADA` (label `Feriado / sem jornada`): horas previstas iguais a
  `00:00` e zero marcações. Severidade `INFORMATIVO`; não é inconsistência e
  não entra em críticos, justificativas ou na taxa de conformidade.
- `OK`: não há ocorrência aplicável.

## Folga, férias e afastamentos

Quando horas previstas são `00:00`, não há marcação e o motivo indica Folga,
Férias, licença, afastamento ou evento equivalente, o registro recebe
`status = SEM_JORNADA` e não é uma inconsistência. A mesma regra vale para
qualquer dia sem carga prevista, mesmo quando o motivo está vazio.

Registros sem jornada e sem marcação recebem `inconsistency_types =
["SEM_JORNADA"]`, para permitir drill-down informativo sem contaminar os
indicadores de inconsistência. O motivo original é preservado.

## Indicadores

- `dias_com_jornada`: registros com `Horas previstas` maiores que zero;
- `dias_sem_jornada`: registros com `Horas previstas` iguais a zero ou
  indisponíveis;
- `feriados_sem_jornada`: dias sem jornada e sem marcações, classificados como
  informativos;
- `ponto_a_justificar`: dias com horas previstas positivas e zero marcações;
- `sem_marcacoes`: alias de compatibilidade de `ponto_a_justificar`;
- `registros_ok`: registros `OK` dentro de `dias_com_jornada`;
- `taxa_conformidade`: `registros_ok / dias_com_jornada * 100`;
- `colaboradores_criticos`: colaboradores distintos com ao menos uma
  ocorrência de severidade `CRITICA`;
- `saldos_finais_negativos`: colaboradores distintos cujo saldo do registro
  cronologicamente mais recente disponível é menor que zero.

O resumo também contém `saldo_finais`, com `employee_name`, `saldo_final` e
`data_saldo_final`, e `distribuicao_horas_previstas`.
