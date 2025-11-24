# ============================================================
# PAINEL VISA IPOJUCA – COM LOGIN E PERMISSÕES
# ============================================================

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

# ------------------------------------------------------------
# 🔐 CONFIGURAÇÃO DE PÁGINA
# ------------------------------------------------------------
st.set_page_config(page_title="Painel VISA Ipojuca", layout="wide")

# ------------------------------------------------------------
# 🔐 LOGIN SYSTEM
# ------------------------------------------------------------
if "auth" not in st.session_state:
    st.session_state["auth"] = None  # None, "admin", "user"

st.title("🔐 Acesso ao Painel da Vigilância Sanitária de Ipojuca")

if st.session_state["auth"] is None:
    with st.form("login_form"):
        st.subheader("Informe suas credenciais para entrar")
        username = st.text_input("Usuário")
        password = st.text_input("Senha", type="password")
        entrar = st.form_submit_button("Entrar")

        if entrar:
            if username == "admin" and password == "Ipojuca@2025*":
                st.session_state["auth"] = "admin"
                st.success("Bem-vindo, administrador!")
                st.experimental_rerun()

            elif username == "antoinio.reldismar" and password == "Visa@2025":
                st.session_state["auth"] = "user"
                st.success("Login realizado!")
                st.experimental_rerun()

            else:
                st.error("❌ Usuário ou senha inválidos.")
    st.stop()

perfil = st.session_state["auth"]
is_admin = perfil == "admin"
is_user = perfil == "user"

# ------------------------------------------------------------
# BOTÃO DE SAIR
# ------------------------------------------------------------
st.sidebar.success(f"Usuário logado: {perfil}")
if st.sidebar.button("Sair"):
    st.session_state["auth"] = None
    st.experimental_rerun()

# ------------------------------------------------------------
# 🟦 LER DADOS DO GOOGLE SHEETS
# ------------------------------------------------------------

GSHEET_URL = "https://docs.google.com/spreadsheets/d/1zsM8Zxdc-MnXSvV_OvOXiPoc1U4j-FOn/edit?usp=sharing"


def converter_para_csv(url):
    parts = url.split("/d/")
    sheet_id = parts[1].split("/")[0]
    return f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"


@st.cache_data(ttl=600)
def carregar_planilha():
    url_csv = converter_para_csv(GSHEET_URL)
    df = pd.read_csv(url_csv)
    return df


df = carregar_planilha()

# Normaliza colunas
df.columns = [c.strip() for c in df.columns]

# Convertendo datas
for col in ["ENTRADA", "1ª INSPEÇÃO", "DATA CONCLUSÃO"]:
    df[col] = pd.to_datetime(df[col], dayfirst=True, errors="coerce")

# Criando ano/mês
df["ANO"] = df["ENTRADA"].dt.year
df["MES"] = df["ENTRADA"].dt.month

# ------------------------------------------------------------
# 🎛️ FILTROS DO SIDEBAR
# ------------------------------------------------------------
st.sidebar.header("🎛️ Filtros")

modo = st.sidebar.radio("Período por:", ["Ano/Mês", "Intervalo de datas"])

if modo == "Ano/Mês":
    anos = sorted(df["ANO"].dropna().unique())
    meses = sorted(df["MES"].dropna().unique())

    sel_ano = st.sidebar.selectbox("Ano", anos)
    sel_mes = st.sidebar.selectbox("Mês", meses)

    df_filtrado = df[(df["ANO"] == sel_ano) & (df["MES"] == sel_mes)]

else:
    inicio = st.sidebar.date_input("Data inicial", df["ENTRADA"].min())
    fim = st.sidebar.date_input("Data final", df["ENTRADA"].max())
    df_filtrado = df[(df["ENTRADA"] >= pd.to_datetime(inicio)) &
                     (df["ENTRADA"] <= pd.to_datetime(fim))]

# Filtro universal: Classificação de Risco
if "CLASSIFICAÇÃO" in df.columns:
    riscos = sorted(df["CLASSIFICAÇÃO"].dropna().unique())
    risco_sel = st.sidebar.multiselect("Classificação", riscos, default=riscos)
    df_filtrado = df_filtrado[df_filtrado["CLASSIFICAÇÃO"].isin(risco_sel)]

# Filtros exclusivos do admin
if is_admin:

    # Território
    if "TERRITÓRIO" in df.columns:
        territorios = sorted(df["TERRITÓRIO"].dropna().unique())
        ter_sel = st.sidebar.multiselect("Território", territorios, default=territorios)
        df_filtrado = df_filtrado[df_filtrado["TERRITÓRIO"].isin(ter_sel)]

    # Coordenação
    if "COORDENAÇÃO" in df.columns:
        coords = sorted(df["COORDENAÇÃO"].dropna().unique())
        coord_sel = st.sidebar.multiselect("Coordenação", coords, default=coords)
        df_filtrado = df_filtrado[df_filtrado["COORDENAÇÃO"].isin(coord_sel)]

# ------------------------------------------------------------
# 🧮 CÁLCULO DOS INDICADORES
# ------------------------------------------------------------

df_tmp = df_filtrado.copy()

# Deadlines
df_tmp["DEADLINE_30"] = df_tmp["ENTRADA"] + timedelta(days=30)
df_tmp["DEADLINE_90"] = df_tmp["ENTRADA"] + timedelta(days=90)

# Indicadores
df_tmp["REALIZOU_30"] = (
    df_tmp["1ª INSPEÇÃO"].notna() &
    (df_tmp["1ª INSPEÇÃO"] <= df_tmp["DEADLINE_30"])
)

df_tmp["FINALIZOU_90"] = (
    df_tmp["DATA CONCLUSÃO"].notna() &
    (df_tmp["DATA CONCLUSÃO"] <= df_tmp["DEADLINE_90"])
)

# KPIs
total_entradas = len(df_tmp)
realizou_30 = df_tmp["REALIZOU_30"].sum()
finalizou_90 = df_tmp["FINALIZOU_90"].sum()

pct_30 = round((realizou_30 / total_entradas) * 100, 2) if total_entradas else 0
pct_90 = round((finalizou_90 / total_entradas) * 100, 2) if total_entradas else 0

# ------------------------------------------------------------
# 🟦 ÁREA PRINCIPAL – DIFERENTE PARA USER E ADMIN
# ------------------------------------------------------------

st.header("📌 Indicadores do Período")

col1, col2, col3 = st.columns(3)
col1.metric("Entradas", total_entradas)
col2.metric("Realizou a inspeção em até 30 dias", f"{pct_30}%")
col3.metric("Finalizou o processo em até 90 dias", f"{pct_90}%")

# Usuário comum vê SOMENTE isso
if is_user:
    st.info("Você está usando o modo de visualização padrão.")
    st.stop()

# ------------------------------------------------------------
# 👑 ADMINISTRADOR – vê tudo
# ------------------------------------------------------------

st.subheader("📊 Tabelas detalhadas")
st.dataframe(df_tmp, use_container_width=True)

# ------------------------------------------------------------
# 📈 GRÁFICOS
# ------------------------------------------------------------

import plotly.express as px

if "COORDENAÇÃO" in df_tmp.columns:
    st.subheader("📈 Inspeções por Coordenação (30/90 dias)")
    df_coord = df_tmp.groupby("COORDENAÇÃO")[["REALIZOU_30", "FINALIZOU_90"]].sum().reset_index()
    fig = px.bar(df_coord, x="COORDENAÇÃO", y=["REALIZOU_30", "FINALIZOU_90"], barmode="group")
    st.plotly_chart(fig, use_container_width=True)

if "TERRITÓRIO" in df_tmp.columns:
    st.subheader("🌍 Inspeções por Território (30/90 dias)")
    df_ter = df_tmp.groupby("TERRITÓRIO")[["REALIZOU_30", "FINALIZOU_90"]].sum().reset_index()
    fig2 = px.bar(df_ter, x="TERRITÓRIO", y=["REALIZOU_30", "FINALIZOU_90"], barmode="group")
    st.plotly_chart(fig2, use_container_width=True)

# ------------------------------------------------------------
# ⚠ PROCESSOS EM ATRASO
# ------------------------------------------------------------

st.subheader("⚠ Processos com atraso")

df_atraso_30 = df_tmp[df_tmp["REALIZOU_30"] == False]
df_atraso_90 = df_tmp[df_tmp["FINALIZOU_90"] == False]

st.write("🔸 Atraso na primeira inspeção")
st.dataframe(df_atraso_30)

st.write("🔸 Atraso na conclusão")
st.dataframe(df_atraso_90)
