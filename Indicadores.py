# painel_avancado.py
import streamlit as st
import pandas as pd
from io import BytesIO
from datetime import timedelta


# =========================================================
# CONFIGURAÇÃO DO PAINEL
# =========================================================
st.set_page_config(page_title="Painel VISA Ipojuca", layout="wide")
st.title("📊 Painel de Produção – Vigilância Sanitária de Ipojuca")


# =========================================================
# URL DA PLANILHA GOOGLE SHEETS
# =========================================================
GSHEET_URL = "https://docs.google.com/spreadsheets/d/1zsM8Zxdc-MnXSvV_OvOXiPoc1U4j-FOn/edit?usp=sharing"


# =========================================================
# CONVERSÃO DE LINK → CSV EXPORT
# =========================================================
def converter_para_csv(url):
    partes = url.split("/d/")
    if len(partes) < 2:
        st.error("URL inválida. Não foi possível extrair ID.")
        return None

    resto = partes[1]
    sheet_id = resto.split("/")[0]

    return f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"


# =========================================================
# CARREGAR PLANILHA DO GOOGLE
# =========================================================
@st.cache_data(ttl=600)
def carregar_planilha_google(url_original):
    url_csv = converter_para_csv(url_original)

    try:
        df = pd.read_csv(url_csv)
    except Exception as e:
        st.error(f"Erro ao carregar planilha do Google Sheets: {e}")
        return pd.DataFrame()

    # Normalização
    df.columns = [c.strip() for c in df.columns]

    # Converte datas
    for col in ["ENTRADA", "1ª INSPEÇÃO", "DATA CONCLUSÃO"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], dayfirst=True, errors="coerce")

    # Ano e mês
    df["ANO_ENTRADA"] = df["ENTRADA"].dt.year
    df["MES_ENTRADA"] = df["ENTRADA"].dt.month

    # Normaliza textos
    if "SITUAÇÃO" in df.columns:
        df["SITUAÇÃO"] = df["SITUAÇÃO"].fillna("").astype(str).str.upper()

    if "CLASSIFICAÇÃO" in df.columns:
        df["CLASSIFICAÇÃO"] = df["CLASSIFICAÇÃO"].fillna("").astype(str).str.title()

    return df


df = carregar_planilha_google(GSHEET_URL)

if df.empty:
    st.stop()


# =========================================================
# SIDEBAR — FILTROS
# =========================================================
st.sidebar.header("Filtros do painel")

modo = st.sidebar.radio("Período por:", ["Ano/Mês", "Intervalo de datas"])


# Nomes dos meses
NOME_MESES = {
    1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril",
    5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto",
    9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro"
}


if modo == "Ano/Mês":
    anos = sorted(df["ANO_ENTRADA"].dropna().unique())
    ano_sel = st.sidebar.selectbox("Ano", anos)

    meses_disp = sorted(df[df["ANO_ENTRADA"] == ano_sel]["MES_ENTRADA"].unique())

    mes_sel = st.sidebar.multiselect(
        "Mês",
        options=meses_disp,
        default=meses_disp,
        format_func=lambda m: NOME_MESES.get(int(m), str(m)),
    )

    df_filtrado = df[
        (df["ANO_ENTRADA"] == ano_sel) &
        (df["MES_ENTRADA"].isin(mes_sel))
    ]

else:
    inicio = st.sidebar.date_input("Início", df["ENTRADA"].min())
    fim = st.sidebar.date_input("Fim", df["ENTRADA"].max())

    df_filtrado = df[
        (df["ENTRADA"].dt.date >= inicio) &
        (df["ENTRADA"].dt.date <= fim)
    ]


# =========================================================
# CÁLCULO DOS INDICADORES (LÓGICA NOVA)
# =========================================================
def calcular_indicadores(df_base, agrupar=True):

    df_tmp = df_base.copy()

    # Deadlines
    df_tmp["DEADLINE_30"] = df_tmp["ENTRADA"] + timedelta(days=30)
    df_tmp["DEADLINE_90"] = df_tmp["ENTRADA"] + timedelta(days=90)

    # Cumprimento das metas
    df_tmp["CUMPRIU_30"] = (
        df_tmp["1ª INSPEÇÃO"].notna() &
        (df_tmp["1ª INSPEÇÃO"] <= df_tmp["DEADLINE_30"])
    )

    df_tmp["CUMPRIU_90"] = (
        df_tmp["DATA CONCLUSÃO"].notna() &
        (df_tmp["DATA CONCLUSÃO"] <= df_tmp["DEADLINE_90"])
    )

    total_entradas = len(df_tmp)

    if agrupar:
        resultados = []

        for (ano, mes), g in df_tmp.groupby(["ANO_ENTRADA", "MES_ENTRADA"]):

            entradas = len(g)
            cumpriram_30 = int(g["CUMPRIU_30"].sum())
            cumpriram_90 = int(g["CUMPRIU_90"].sum())

            resultados.append({
                "Ano": ano,
                "Mês": NOME_MESES.get(mes, mes),
                "Entradas": entradas,
                "Cumpriram 30 dias": cumpriram_30,
                "% 30 dias": round((cumpriram_30 / entradas) * 100, 2) if entradas else 0,
                "Cumpriram 90 dias": cumpriram_90,
                "% 90 dias": round((cumpriram_90 / entradas) * 100, 2) if entradas else 0,
            })

        return pd.DataFrame(resultados)

    else:
        cumpriram_30 = int(df_tmp["CUMPRIU_30"].sum())
        cumpriram_90 = int(df_tmp["CUMPRIU_90"].sum())

        return pd.DataFrame([{
            "Entradas": total_entradas,
            "Cumpriram 30 dias": cumpriram_30,
            "% 30 dias": round((cumpriram_30 / total_entradas) * 100, 2) if total_entradas else 0,
            "Cumpriram 90 dias": cumpriram_90,
            "% 90 dias": round((cumpriram_90 / total_entradas) * 100, 2) if total_entradas else 0,
        }])


agrupar = True if modo == "Ano/Mês" else False
df_ind = calcular_indicadores(df_filtrado, agrupar)


# =========================================================
# EXIBIÇÃO DOS INDICADORES
# =========================================================
st.subheader("📌 Indicadores Ajustados")
st.dataframe(df_ind, use_container_width=True)

if not df_ind.empty:
    if agrupar:
        linha = df_ind.iloc[-1]
    else:
        linha = df_ind.iloc[0]

    col1, col2 = st.columns(2)
    col1.metric("1ª Inspeção ≤ 30 dias", f"{linha['% 30 dias']}%")
    col2.metric("Conclusão ≤ 90 dias", f"{linha['% 90 dias']}%")


# =========================================================
# ATRASOS
# =========================================================
st.subheader("⚠ Processos com atraso")

df_filtrado["DEADLINE_30"] = df_filtrado["ENTRADA"] + timedelta(days=30)
df_filtrado["DEADLINE_90"] = df_filtrado["ENTRADA"] + timedelta(days=90)

atraso_30 = df_filtrado[
    (df_filtrado["1ª INSPEÇÃO"].isna()) |
    (df_filtrado["1ª INSPEÇÃO"] > df_filtrado["DEADLINE_30"])
]

atraso_90 = df_filtrado[
    (df_filtrado["DATA CONCLUSÃO"].isna()) |
    (df_filtrado["DATA CONCLUSÃO"] > df_filtrado["DEADLINE_90"])
]

st.markdown("### 🔸 Atraso na primeira inspeção")
st.dataframe(atraso_30, use_container_width=True)

st.markdown("### 🔸 Atraso na conclusão")
st.dataframe(atraso_90, use_container_width=True)


# =========================================================
# DOWNLOAD DO RELATÓRIO
# =========================================================
def gerar_excel(dados, resumo):
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        dados.to_excel(writer, sheet_name="Filtrado", index=False)
        resumo.to_excel(writer, sheet_name="Indicadores", index=False)
    return buffer.getvalue()


st.download_button(
    label="📥 Baixar relatório Excel",
    data=gerar_excel(df_filtrado, df_ind),
    file_name="relatorio_visa.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)


st.caption("Painel da Vigilância Sanitária de Ipojuca – versão revisada ✔️")
