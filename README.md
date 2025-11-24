# Painel de Inspeções - Vigilância Sanitária de Ipojuca

## 🔍 Funcionalidades

- Filtros dinâmicos por:
  - Protocolo
  - CNPJ
  - Estabelecimento
  - Atividade
  - Classificação
  - Território
  - Situação (ordenado alfabeticamente)
  - Entrada (seletor de datas)

- Resumo da seleção quando escolhido um único protocolo.

- Indicadores de Desempenho:
  - **🕒 1ª Visita em até 30 dias**
    - Considera processos cuja 1ª inspeção ocorreu até a data prevista.
    - Exclui situações: "AGUARDANDO 1ª INSPEÇÃO" e "PENDÊNCIA DOCUMENTAL".
  - **📜 Processo finalizado em até 90 dias**
    - Considera processos concluídos até a previsão de conclusão.
    - Exclui situações: "EM INSPEÇÃO", "AGUARDANDO 1ª INSPEÇÃO" e "PENDÊNCIA DOCUMENTAL".

- Gráfico das justificativas dos **INDEFERIDOS**.

- Visualização de:
  - Dados filtrados
  - Gráficos interativos

- Download de relatório Excel com:
  - Dados Filtrados
  - Resumo dos Indicadores
  - Justificativas dos Indeferidos

---

## 🚀 Como Executar

1. Clone este repositório.
2. Instale as dependências:
   ```bash
   pip install -r requirements.txt