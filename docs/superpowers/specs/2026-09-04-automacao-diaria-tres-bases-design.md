# Automação diária das três bases

## Objetivo

Atualizar automaticamente todos os dias, às 09:00 no horário de São Paulo, as bases de inconsistências de jornada, faltas e atrasos usando o Ponto VR, mantendo os botões de atualização manual existentes.

## Decisões

- A data automática será D-1, seguindo o comportamento já usado pelo agendador atual.
- Os três relatórios serão processados em sequência, nunca em paralelo.
- Cada relatório terá configuração própria de tipo, modelo e extensão esperada.
- Os nomes dos modelos serão obrigatórios na configuração; o sistema não escolherá um modelo por aproximação.
- O botão manual continuará usando seus endpoints e seu fluxo atuais.
- A falha de uma base não impedirá a tentativa das outras duas.
- Uma base anterior só será substituída depois de download, parsing, validação e persistência bem-sucedidos.
- Arquivos temporários, cookies e credenciais permanecerão fora do Git e serão removidos ao final de cada etapa.

## Fluxo automático

1. O Agendador de Tarefas do Windows inicia `automation.run_scheduled` às 09:00.
2. O processo adquire uma trava exclusiva para impedir execução duplicada.
3. O robô acessa o Ponto VR e baixa o relatório de inconsistências com o modelo configurado.
4. O arquivo é enviado ao endpoint automático de inconsistências e o processo aguarda a conclusão.
5. O robô baixa o relatório de faltas com o tipo/modelo configurado, envia ao endpoint automático de faltas e aguarda a conclusão.
6. O robô baixa o relatório de atrasos com o tipo/modelo configurado, envia ao endpoint automático de atrasos e aguarda a conclusão.
7. Cada etapa registra somente status, data, duração e código de erro sanitizado.
8. A trava é liberada mesmo quando uma etapa falha.

Cada etapa terá timeout próprio. O próximo relatório só começará depois que o anterior terminar ou atingir seu timeout; não será usado um `sleep` fixo para simular espera.

## Configuração do Ponto VR

Além das credenciais já existentes, a automação usará variáveis separadas:

```text
PONTO_JOURNEY_REPORT_TYPE
PONTO_JOURNEY_REPORT_MODEL
PONTO_ABSENCE_REPORT_TYPE
PONTO_ABSENCE_REPORT_MODEL
PONTO_DELAY_REPORT_TYPE
PONTO_DELAY_REPORT_MODEL
PONTO_JOB_TIMEOUT_SECONDS
```

Os parâmetros confirmados para o Ponto VR são:

| Base | Tipo do relatório | Modelo | Formato |
|---|---|---|---|
| Inconsistência | `Jornada (espelho ponto)` | `ROBERT - DASHBOARD` | PDF |
| Falta | `Faltas` | `ROBERT - PAINEL GERENCIAL` | XLS |
| Atraso | `Atrasos` | `ROBERT - DASHBOARD` | XLS |

Os três tipos e modelos serão enviados ao fluxo de download por configuração, sem aproximação de texto. O formato esperado também será validado antes do processamento de cada base.

## Endpoints automáticos

- `POST /api/automation/report`: mantém a jornada em PDF.
- `POST /api/automation/absence`: recebe o Excel de faltas e persiste somente após validação.
- `POST /api/automation/delay`: recebe o Excel de atrasos e persiste somente após validação.

Os novos endpoints usarão `AUTOMATION_TOKEN`, aceitarão somente arquivos do formato esperado, validarão que o período corresponde a D-1 e não exigirão sessão de navegador. Os endpoints administrativos manuais não serão removidos nem alterados para depender da automação.

## Falhas e idempotência

- Um hash do arquivo impede duplicação acidental.
- Se o Ponto VR não responder, o relatório atual daquela base permanece ativo.
- Se o parser rejeitar o arquivo ou detectar período/modelo incorreto, a base anterior permanece ativa.
- A execução diária retorna um resumo das três etapas, permitindo identificar qual base falhou.
- O instalador do agendador removerá os horários antigos e registrará somente 09:00.

## Testes

- Testar a seleção independente de tipo/modelo para cada relatório.
- Testar que os três jobs são executados em ordem e que o segundo/terceiro continuam após falha do anterior.
- Testar timeout individual e liberação da trava.
- Testar que o endpoint automático de faltas persiste uma base válida e rejeita uma inválida.
- Testar que o endpoint automático de atrasos persiste uma base válida e rejeita uma inválida.
- Testar que os endpoints e botões manuais continuam disponíveis.
- Executar os testes Python, TypeScript, typecheck e build.
