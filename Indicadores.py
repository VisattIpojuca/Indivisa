import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import plotly.express as px
from io import BytesIO

# --------------------------------------------------------
# CONFIGURAÇÃO INICIAL
# --------------------------------------------------------
st.set_page_config(page_title="Painel VISA Ipojuca", layout="wide")

# --------------------------------------------------------
# LOGIN — usuários e permissões
# --------------------------------------------------------
USERS = {
    "admin": {
        "password": "Ipojuca@2025*",
        "role": "admin"
    },
    "antonio.reldismar": {
        "password": "Visa@2025",
        "role": "standard"
    }
}

if "logged" not in st.session_state:
    st.session_state.logged = False
    st.session_state.user = None
    st.session_state.role = None


def do_login(username, password):
    if username in USERS and USERS[username]["password"] == password:
        st.session_state.logged = True
        st.session_state.user = username
        st.session_state.role = USERS[username]["role"]
        return True
    return False


def do_logout():
    st.session_state.logged = False
    st.session_state.user = None
    st.session_state.role = None
    st.experimental_rerun()


# --------------------------------------------------------
# TELA DE LOGIN ANTES DO PAINEL
# --------------------------------------------------------
if not st.session_state.logged:
    st.title("🔐 Painel VISA Ipojuca — Login")

    with st.form("login_form"):
        username = st.text_input("Usuário")
        password = st.text_input("Senha", type="password")
        submit = st.form_submit_button("Entrar")

        if submit:
            if not do_login(username.strip(), password):
                st.error("Usuário ou senha incorretos.")

    st.stop()

# --------------------------------------------------------
# CARREGANDO DADOS DO GOOGLE SHEETS
# --------------------------------------------------------
GSHEET_URL = "https://docs.google.com/spreadsheets/d/1zsM8Zxdc-MnXSvV_OvOXiPoc1U4j-FOn/edit?usp=sharing"


def converter_para_csv(url):
    sheet_id = url.split("/d/")[1].split("/")[0]
    return f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"


@st.cache_data(ttl=600)
def carregar_planilha_google():
    csv_url = converter_para_csv(GSHEET_URL)
    df = pd.read_csv(csv_url)

    df.columns = [c.strip() for c in df.columns]

    for col in ["ENTRADA", "1ª INSPEÇÃO", "DATA CONCLUSÃO"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], dayfirst=True, errors="coerce")

    df["ANO_ENTRADA"] = df["ENTRADA"].dt.year
    df["MES_ENTRADA"] = df["ENTRADA"].dt.month

    return df


df = carregar_planilha_google()

if df.empty:
    st.error("Erro ao carregar Google Sheets.")
    st.stop()

# --------------------------------------------------------
# PAPEL DO USUÁRIO
# --------------------------------------------------------
is_admin = st.session_state.role == "admin"
is_standard = st.session_state.role == "standard"

# --------------------------------------------------------
# MAPEAMENTO DE MESES
# --------------------------------------------------------
NOME_MESES = {
    1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril",
    5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto",
    9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro"
}

ANO_ATUAL = datetime.now().year

# --------------------------------------------------------
# FILTROS
# --------------------------------------------------------
st.sidebar.title(f"Bem-vindo, {st.session_state.user}")

modo = st.sidebar.radio("Período por:", ["Ano/Mês", "Intervalo de datas"])

anos = sorted(df["ANO_ENTRADA"].dropna().unique())
default_ano = ANO_ATUAL if ANO_ATUAL in anos else max(anos)

if modo == "Ano/Mês":
    ano = st.sidebar.selectbox("Ano", anos, index=anos.index(default_ano))
    meses_disp = sorted(df[df["ANO_ENTRADA"] == ano]["MES_ENTRADA"].dropna().unique())
    meses = st.sidebar.multiselect(
        "Mês",
        meses_disp,
        default=meses_disp,
        format_func=lambda m: NOME_MESES[m]
    )
else:
    inicio = st.sidebar.date_input("Data inicial", df["ENTRADA"].min())
    fim = st.sidebar.date_input("Data final", df["ENTRADA"].max())

# Classificação (todos podem ver)
classificacoes = sorted(df["CLASSIFICAÇÃO"].dropna().unique()) if "CLASSIFICAÇÃO" in df.columns else []
sel_risco = st.sidebar.multiselect("Classificação de Risco", classificacoes, default=classificacoes)

# Território / Coordenação — só admin vê
col_territorio = next((c for c in df.columns if "TERR" in c.upper()), None)
col_coord = next((c for c in df.columns if "COORD" in c.upper()), None)

if is_admin:
    if col_territorio:
        territorios = sorted(df[col_territorio].dropna().unique())
        sel_ter = st.sidebar.multiselect("Território", territorios, default=territorios)
    else:
        sel_ter = []

    if col_coord:
        coords = sorted(df[col_coord].dropna().unique())
        sel_coord = st.sidebar.multiselect("Coordenação", coords, default=coords)
    else:
        sel_coord = []
else:
    sel_ter = []
    sel_coord = []

# Logout
if st.sidebar.button("Sair do sistema"):
    do_logout()

# --------------------------------------------------------
# APLICANDO FILTROS
# --------------------------------------------------------
f = df.copy()

if modo == "Ano/Mês":
    f = f[(f["ANO_ENTRADA"] == ano) & (f["MES_ENTRADA"].isin(meses))]
else:
    f = f[(f["ENTRADA"].dt.date >= inicio) & (f["ENTRADA"].dt.date <= fim)]

if sel_risco:
    f = f[f["CLASSIFICAÇÃO"].isin(sel_risco)]

if is_admin and sel_ter:
    f = f[f[col_territorio].isin(sel_ter)]

if is_admin and sel_coord:
    f = f[f[col_coord].isin(sel_coord)]

# --------------------------------------------------------
# CÁLCULO DOS INDICADORES
# --------------------------------------------------------
f["DEADLINE_30"] = f["ENTRADA"] + timedelta(days=30)
f["DEADLINE_90"] = f["ENTRADA"] + timedelta(days=90)

f["REALIZOU_30"] = (f["1ª INSPEÇÃO"].notna()) & (f["1ª INSPEÇÃO"] <= f["DEADLINE_30"])
f["FINALIZOU_90"] = (f["DATA CONCLUSÃO"].notna()) & (f["DATA CONCLUSÃO"] <= f["DEADLINE_90"])

# --------------------------------------------------------
# RESUMO
# --------------------------------------------------------
entradas = len(f)
realizou30 = f["REALIZOU_30"].sum()
finalizou90 = f["FINALIZOU_90"].sum()

p30 = round((realizou30 / entradas) * 100, 2) if entradas else 0
p90 = round((finalizou90 / entradas) * 100, 2) if entradas else 0

# --------------------------------------------------------
# MOSTRANDO OS INDICADORES
# --------------------------------------------------------
st.header("📌 Indicadores do Período")

col1, col2, col3 = st.columns(3)

col1.metric("Entradas", entradas)
col2.metric("Realizou a inspeção em até 30 dias (%)", f"{p30}%")
col3.metric("Finalizou o processo em até 90 dias (%)", f"{p90}%")

st.dataframe(
    f[[
        "ENTRADA", "1ª INSPEÇÃO", "DATA CONCLUSÃO",
        "REALIZOU_30", "FINALIZOU_90",
        "DEADLINE_30", "DEADLINE_90"
    ]],
    use_container_width=True
)

# --------------------------------------------------------
# GRÁFICOS — APENAS PARA ADMIN
# --------------------------------------------------------
if is_admin:
    st.header("📊 Gráficos por Território e Coordenação")

    if col_coord:
        fig = px.bar(
            f.groupby(col_coord).agg(
                Realizou_30=("REALIZOU_30", "sum"),
                Finalizou_90=("FINALIZOU_90", "sum")
            ).reset_index(),
            x=col_coord,
            y=["Realizou_30", "Finalizou_90"],
            title="Indicadores por Coordenação"
        )
        st.plotly_chart(fig, use_container_width=True)

    if col_territorio:
        fig2 = px.bar(
            f.groupby(col_territorio).agg(
                Realizou_30=("REALIZOU_30", "sum"),
                Finalizou_90=("FINALIZOU_90", "sum")
            ).reset_index(),
            x=col_territorio,
            y=["Realizou_30", "Finalizou_90"],
            title="Indicadores por Território"
        )
        st.plotly_chart(fig2, use_container_width=True)

# --------------------------------------------------------
# ATRASADOS — SOMENTE ADMIN
# --------------------------------------------------------
if is_admin:
    st.header("⚠ Processos com atraso")

    atraso_30 = f[f["REALIZOU_30"] == False]
    atraso_90 = f[f["FINALIZOU_90"] == False]

    st.subheader("🔸 Atraso na primeira inspeção")
    st.dataframe(atraso_30, use_container_width=True)

    st.subheader("🔸 Atraso na conclusão")
    st.dataframe(atraso_90, use_container_width=True)
