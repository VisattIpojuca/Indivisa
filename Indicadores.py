# painel_avancado.py
import streamlit as st
import pandas as pd
from io import BytesIO
from datetime import timedelta

# ---------------------------------------------------------
# CONFIGURAÇÃO INICIAL DO PAINEL
# ---------------------------------------------------------
st.set_page_config(page_title="Painel VISA Ipojuca", layout="wide")
st.title("📊 Painel de Produção – Vigilância Sanitária de Ipojuca")


# ---------------------------------------------------------
# FUNÇÃO PARA CONVERTER O LINK DO GOOGLE SHEETS EM CSV
# ---------------------------------------------------------
GSHEET_URL = "https://docs.google.com/spreadsheets/d/1zsM8Zxdc-MnXSvV_OvOXiPoc1U4j-FOn/edit?usp=sharing"

def converter_para_csv(url):
    """Extrai o ID da planilha e gera URL de exportação CSV."""
    try:
        partes = url.split("/d/")
        if len(partes) < 2:
            raise ValueError("URL inválida — não contém /d/.")

        resto = partes[1]
        sheet_id = resto.split("/")[0]

        return f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"

    except Exception as e:
        st.error(f"Erro ao converter URL: {e}")
        return None


# ---------------------------------------------------------
# FUNÇÃO PARA CARREGAR A PLANILHA DIRETAMENTE DO GOOGLE SHEETS
# ---------------------------------------------------------
@st.cache_data(ttl=600)
def carregar_planilha_google(url_original):
    url_csv = converter_para_csv(url_original)
    try:
        df = pd.read_csv(url_csv)
    except Exception as e:
        st.error(f"Erro ao tentar ler a planilha Google Sheets: {e}")
        return pd.DataFrame()

    # Normaliza nomes
    df.columns = [c.strip() for c in df.columns]

    # Converte datas
    for col in ['ENTRADA', '1ª INSPEÇÃO', 'DATA CONCLUSÃO']:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], dayfirst=True, errors='coerce')

    # Cria colunas auxiliares
    df["ANO_ENTRADA"] = df["ENTRADA"].dt.year
    df["MES_ENTRADA"] = df["ENTRADA"].dt.month

    # Normaliza textos
    if "SITUAÇÃO" in df.columns:
        df["SITUAÇÃO"] = df["SITUAÇÃO"].fillna("").astype(str).str.upper()

    if "CLASSIFICAÇÃO" in df.columns:
        df["CLASSIFICAÇÃO"] = df["CLASSIFICAÇÃO"].fillna("").astype(str).str.title()

    return df


# ---------------------------------------------------------
# CARREGA A PLANILHA
# ---------------------------------------------------------
df = carregar_planilha_google(GSHEET_URL)

if df.empty:
    st.error("Nenhum dado encontrado na planilha.")
    st.stop()


# ---------------------------------------------------------
# SIDEBAR — FILTROS
# ---------------------------------------------------------
st.sidebar.header("Filtros do Painel")

modo = st.sidebar.radio("Selecionar período por:", ["Ano/Mês", "Intervalo de datas"])

if modo == "Ano/Mês":
    anos = sorted(df["ANO_ENTRADA"].dropna().unique(), reverse=True)
    ano_sel = st.sidebar.selectbox("Ano:", anos)

    meses = sorted(df[df["ANO_ENTRADA"] == ano_sel]["MES_ENTRADA"].dropna().unique())
    mes_sel = st.sidebar.multiselect("Mês:", meses, default=meses)

    df_filtrado = df[(df["ANO_ENTRADA"] == ano_sel) & (df["MES_ENTRADA"].isin(mes_sel))]

else:
    inicio = st.sidebar.date_input("Data inicial:", df["ENTRADA"].min())
    fim = st.sidebar.date_input("Data final:", df["ENTRADA"].max())

    df_filtrado = df[(df["ENTRADA"].dt.date >= inicio) & (df["ENTRADA"].dt.date <= fim)]


# ---------------------------------------------------------
# CÁLCULO DOS INDICADORES
# ---------------------------------------------------------
def calcular_indicadores(df_base, agrupar=True):

    df_temp = df_base.copy()

    # Deadlines das metas
    df_temp["DEADLINE_30"] = df_temp["ENTRADA"] + timedelta(days=30)
    df_temp["DEADLINE_90"] = df_temp["ENTRADA"] + timedelta(days=90)

    # Condições de cumprimento
    df_temp["CUMPRIU_30"] = (
        df_temp["1ª INSPEÇÃO"].notna() &
        (df_temp["1ª INSPEÇÃO"] <= df_temp["DEADLINE_30"])
    )

    df_temp["CUMPRIU_90"] = (
        df_temp["DATA CONCLUSÃO"].notna() &
        (df_temp["DATA CONCLUSÃO"] <= df_temp["DEADLINE_90"])
    )

    total_entradas = len(df_temp)

    if agrupar:
        resultados = []

        for (ano, mes), g in df_temp.groupby(["ANO_ENTRADA", "MES_ENTRADA"]):

            entradas = len(g)

            cumpriram_30 = int(g["CUMPRIU_30"].sum())
            cumpriram_90 = int(g["CUMPRIU_90"].sum())

            indicadores = {
                "Ano": ano,
                "Mês": mes,
                "Entradas": entradas,
                "Cumpriram 30 dias": cumpriram_30,
                "% 30 dias": round((cumpriram_30 / entradas) * 100, 2) if entradas else 0,
                "Cumpriram 90 dias": cumpriram_90,
                "% 90 dias": round((cumpriram_90 / entradas) * 100, 2) if entradas else 0,
            }

            resultados.append(indicadores)

        return pd.DataFrame(resultados).sort_values(["Ano", "Mês"])

    else:
        cumpriram_30 = int(df_temp["CUMPRIU_30"].sum())
        cumpriram_90 = int(df_temp["CUMPRIU_90"].sum())

        return pd.DataFrame([{
            "Entradas": total_entradas,
            "Cumpriram 30 dias": cumpriram_30,
            "% 30 dias": round((cumpriram_30 / total_entradas) * 100, 2) if total_entradas else 0,
            "Cumpriram 90 dias": cumpriram_90,
            "% 90 dias": round((cumpriram_90 / total_entradas) * 100, 2) if total_entradas else 0,
        }])


agrupar = True if modo == "Ano/Mês" else False
df_ind = calcular_indicadores(df_filtrado, agrupar)


# ---------------------------------------------------------
# EXIBIÇÃO DOS INDICADORES
# ---------------------------------------------------------
st.subheader("📌 Indicadores do Período Selecionado")
st.dataframe(df_ind, use_container_width=True)

if not df_ind.empty:
    if agrupar:
        linha = df_ind.iloc[-1]
    else:
        linha = df_ind.iloc[0]

    col1, col2 = st.columns(2)
    col1.metric("1ª Inspeção ≤ 30 dias", f"{linha['% 30d']}%")
    col2.metric("Conclusão ≤ 90 dias", f"{linha['% 90d']}%")


# ---------------------------------------------------------
# PROCESSOS ATRASADOS
# ---------------------------------------------------------
st.subheader("⚠ Processos com atraso")

df_filtrado["DEADLINE_1A"] = df_filtrado["ENTRADA"] + timedelta(days=30)
df_filtrado["DEADLINE_90"] = df_filtrado["ENTRADA"] + timedelta(days=90)

atraso_1a = df_filtrado[
    (df_filtrado["1ª INSPEÇÃO"].isna()) | (df_filtrado["1ª INSPEÇÃO"] > df_filtrado["DEADLINE_1A"])
]

atraso_90 = df_filtrado[
    (df_filtrado["DATA CONCLUSÃO"].isna()) | (df_filtrado["DATA CONCLUSÃO"] > df_filtrado["DEADLINE_90"])
]

st.markdown("### 🔸 Atraso na 1ª inspeção")
st.dataframe(atraso_1a, use_container_width=True)

st.markdown("### 🔸 Atraso na conclusão (≤ 90 dias)")
st.dataframe(atraso_90, use_container_width=True)


# ---------------------------------------------------------
# DOWNLOAD DOS DADOS
# ---------------------------------------------------------
def gerar_excel(dados, resumo):
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        dados.to_excel(writer, sheet_name="Filtrado", index=False)
        resumo.to_excel(writer, sheet_name="Indicadores", index=False)
    return buffer.getvalue()


st.download_button(
    label="📥 Baixar relatório completo (Excel)",
    data=gerar_excel(df_filtrado, df_ind),
    file_name="relatorio_visa.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)


st.caption("Painel desenvolvido para a Vigilância Sanitária de Ipojuca – versão Google Sheets 🌐")
