# Layout do PDF Jornada

O arquivo inicial contém uma seção por colaborador e linhas diárias com data,
seis posições possíveis de ponto, totais calculados, horas previstas, saldo e
motivo/observação. O layout é textual, mas os valores são fragmentados em
comandos PDF posicionados por coordenadas.

O parser usa o texto Unicode exposto pelo `pypdf`, agrupa fragmentos por linha
e associa as células às colunas por posição aproximada. A página de origem é
armazenada para auditoria. Uma mudança relevante de layout deve gerar teste e
revisão antes de processar PDFs de produção.
