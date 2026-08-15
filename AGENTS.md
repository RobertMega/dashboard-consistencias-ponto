# Dashboard de Consistências de Ponto

Este projeto é independente do projeto Dashboard-solicitacoes-ponto.

## Regra principal

Nunca modificar arquivos fora deste repositório.

Nunca modificar ou acessar para escrita:
- dashboard-solicitacoes-ponto
- solicitacoes_ponto_repo

Todo código novo deve permanecer dentro de dashboard-consistencias-ponto.

## Objetivo

Criar uma solução gerencial para análise de inconsistências de ponto a partir do relatório PDF de Jornada.

A solução terá:

- leitura do PDF;
- extração das jornadas previstas;
- extração das marcações realizadas;
- identificação de inconsistências;
- geração de base normalizada;
- geração de Excel;
- dashboard web;
- posteriormente automação diária D-1.

## Estrutura desejada

web/
automation/
  parser/
  download/
  export/
  tests/
docs/
samples/
references/

## Segurança

Nunca versionar:
- .env
- credenciais
- cookies
- tokens
- PDFs reais de produção
- dados pessoais de produção

## Ordem de desenvolvimento

1. Validar leitura do PDF.
2. Criar e testar parser.
3. Implementar regras de inconsistência.
4. Validar indicadores.
5. Criar Excel.
6. Criar dashboard.
7. Somente depois automatizar login e download D-1.

Não começar pela automação do login.

## Dashboard

É um dashboard gerencial para coordenadores, gerentes e diretores.

Não exibir matrícula de colaboradores.

Usar como referência visual:

references/dashboard-referencia.png

Usar o logo:

references/logo-motoprama.png

## PDF

Usar inicialmente:

samples/jornada-exemplo.pdf

Nunca inventar informações ausentes no PDF.