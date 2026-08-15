# Regras de inconsistência

As regras vigentes estão documentadas integralmente em
[`REGRAS_NEGOCIO.md`](REGRAS_NEGOCIO.md). Esta tabela é um resumo do contrato.

| Código | Regra |
| --- | --- |
| `PONTO_A_JUSTIFICAR` | Jornada prevista positiva sem marcações realizadas; não presume falta. |
| `MARCACAO_IMPAR` | Jornada válida com quantidade de marcações ímpar. |
| `MARCACOES_INCOMPLETAS` | Quantidade par, positiva e menor que a expectativa derivada dos slots previstos. |
| `PONTOS_SEM_JORNADA` | Há marcações quando não há jornada prevista válida. |
| `SEM_JORNADA` | Dia sem jornada prevista e sem marcações; informativo, não é inconsistência. |
| `CONFLITO_JORNADA_EVENTO` | Evento justificativo coexistindo com jornada prevista. |
| `MAIS_QUE_PREVISTO` | Quantidade de marcações maior que a expectativa; nunca usa horas. |
| `OK` | Nenhuma regra aplicável. |

Folga, férias, afastamentos, INSS, licença maternidade e desligamento sem
jornada prevista recebem `SEM_JORNADA` e não são inconsistências.
