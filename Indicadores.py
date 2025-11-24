# Painel VISA Ipojuca — Versão corrigida (Google Sheets ativo)
# Requisitos: streamlit, pandas, plotly, xlsxwriter

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from io import BytesIO
import plotly.express as px

# --------------------------------------------------------
# CONFIGURAÇÃO DA PÁGINA
# --------------------------------------------------------
st.set_page_config(page_title="Painel VISA Ipojuca", layout="wide")

# --------------------------------------------------------
# FONTE DE DADOS: GOOGLE SHEETS
# --------------------------------------------------------
GOOGLE_SHEETS_URL = (
    "https://docs.google.com/spreadsheets/d/"
    "1zsM8Zxdc-MnXSvV_OvOXiPoc1U4j-FOn/gviz/tq?tqx=out:csv"
)

def carregar_planilha_google():
    """Carrega a primeira aba da planilha do Google Sheets como CSV."""
    try:
        df = pd.read_csv(GOOGLE_SHEETS_URL)
    except Exception as e:
        st.error(f"Erro ao carregar Google Sheets: {e}")
        return pd.DataFrame()

    df.columns = [str(c).strip() for c in df.columns]

    for col in ["ENTRADA", "1ª INSPEÇÃO", "DATA CONCLUSÃO"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], dayfirst=True, errors="coerce")

    if "ENTRADA" in df.columns:
        df["ANO_ENTRADA"] = df["ENTRADA"].dt.year
        df["MES_ENTRADA"] = df["ENTRADA"].dt.month
    else:
        df["ANO_ENTRADA"] = pd.NA
        df["MES_ENTRADA"] = pd.NA

    if "SITUAÇÃO" in df.columns:
        df["SITUAÇÃO"] = df["SITUAÇÃO"].fillna("").astype(str).str.upper()
    if "CLASSIFICAÇÃO" in df.columns:
        df["CLASSIFICAÇÃO"] = df["CLASSIFICAÇÃO"].fillna("").astype(str).str.title()

    return df

# --------------------------------------------------------
# GERAR EXCEL
# --------------------------------------------------------
def gerar_excel_bytes(dfs: dict):
    out = BytesIO()
    with pd.ExcelWriter(out, engine="xlsxwriter") as writer:
        for name, d in dfs.items():
            try:
                d.to_excel(writer, sheet_name=str(name)[:31], index=False)
            except Exception:
                d.to_excel(writer, sheet_name="sheet", index=False)
    return out.getvalue()

# --------------------------------------------------------
# USUÁRIOS
# --------------------------------------------------------
USERS = {
    "admin": {"password": "Ipojuca@2025*", "role": "admin"},
    "antonio.reldismar": {"password": "Visa@2025", "role": "standard"}
}

# --------------------------------------------------------
# LOGIN / SESSÃO
# --------------------------------------------------------
if "logged" not in st.session_state:
    st.session_state["logged"] = False
    st.session_state["user"] = None
    st.session_state["role"] = None

def do_login(username: str, password: str) -> bool:
    username = (username or "").strip()
    if username in USERS and USERS[username]["password"] == (password or ""):
        st.session_state["logged"] = True
        st.session_state["user"] = username
        st.session_state["role"] = USERS[username]["role"]
        return True
    return False

def do_logout():
    st.session_state["logged"] = False
    st.session_state["user"] = None
    st.session_state["role"] = None
    st.experimental_rerun()

if not st.session_state["logged"]:
    st.title("🔐 Painel VISA Ipojuca — Acesso")
    with st.form("login_form"):
        user_input = st.text_input("Usuário")
        pass_input = st.text_input("Senha", type="password")
        submitted = st.form_submit_button("Entrar")
        if submitted:
            if not do_login(user_input, pass_input):
                st.error("Usuário ou senha incorretos.")
    st.stop()

# --------------------------------------------------------
# CARREGAR DADOS (USANDO GOOGLE SHEETS)
# --------------------------------------------------------
df = carregar_planilha_google()

if df.empty:
    st.error("⚠ Não foi possível carregar a planilha do Google Sheets.")
    st.stop()

# --------------------------------------------------------
# PERFIL
# --------------------------------------------------------
is_admin = st.session_state["role"] == "admin"
is_standard = st.session_state["role"] == "standard"

# --------------------------------------------------------
# MAPA DE MESES
# --------------------------------------------------------
NOME_MESES = {
    1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril",
    5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto",
    9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro"
}
ANO_ATUAL = datetime.now().year

# --------------------------------------------------------
# SIDEBAR
# --------------------------------------------------------
st.sidebar.header(f"Olá, {st.session_state['user']} ({st.session_state['role']})")

modo = st.sidebar.radio("Período por:", ["Ano/Mês", "Intervalo de datas"])

anos = sorted(df["ANO_ENTRADA"].dropna().unique())
default_ano = ANO_ATUAL if ANO_ATUAL in anos else (max(anos) if anos else ANO_ATUAL)

if modo == "Ano/Mês":
    ano_sel = st.sidebar.selectbox("Ano", anos, index=anos.index(default_ano))
    meses_disp = sorted(df[df["ANO_ENTRADA"] == ano_sel]["MES_ENTRADA"].dropna().unique())
    mes_sel = st.sidebar.multiselect(
        "Mês", options=meses_disp, default=meses_disp,
        format_func=lambda m: NOME_MESES.get(int(m), str(m))
    )
else:
    inicio = st.sidebar.date_input("Data início", df["ENTRADA"].min().date())
    fim = st.sidebar.date_input("Data fim", df["ENTRADA"].max().date())

# Classificação
if "CLASSIFICAÇÃO" in df.columns:
    riscos = sorted(df["CLASSIFICAÇÃO"].dropna().unique())
else:
    riscos = []
sel_risco = st.sidebar.multiselect("Classificação (Risco)", riscos, default=riscos)

# Território/Coordenação detectados dinamicamente
col_territorio = next((c for c in df.columns if "TERR" in c.upper()), None)
col_coord = next((c for c in df.columns if "COORD" in c.upper()), None)

sel_ter = []
sel_coord = []

if is_admin and col_territorio:
    territorios = sorted(df[col_territorio].dropna().unique())
    sel_ter = st.sidebar.multiselect("Território", territorios, default=territorios)

if is_admin and col_coord:
    coords = sorted(df[col_coord].dropna().unique())
    sel_coord = st.sidebar.multiselect("Coordenação", coords, default=coords)

if st.sidebar.button("Sair / Logout"):
    do_logout()

# --------------------------------------------------------
# APLICAR FILTROS
# --------------------------------------------------------
f = df.copy()

if modo == "Ano/Mês":
    f = f[(f["ANO_ENTRADA"] == ano_sel) & (f["MES_ENTRADA"].isin(mes_sel))]
else:
    f = f[(f["ENTRADA"].dt.date >= inicio) & (f["ENTRADA"].dt.date <= fim)]

if sel_risco:
    f = f[f["CLASSIFICAÇÃO"].isin(sel_risco)]

if is_admin and sel_ter:
    f = f[f[col_territorio].isin(sel_ter)]

if is_admin and sel_coord:
    f = f[f[col_coord].isin(sel_coord)]

# --------------------------------------------------------
# DEADLINES
# --------------------------------------------------------
f["DEADLINE_30"] = f["ENTRADA"] + timedelta(days=30)
f["DEADLINE_90"] = f["ENTRADA"] + timedelta(days=90)

f["REALIZOU_30"] = f["1ª INSPEÇÃO"].notna() & (f["1ª INSPEÇÃO"] <= f["DEADLINE_30"])
f["FINALIZOU_90"] = f["DATA CONCLUSÃO"].notna() & (f["DATA CONCLUSÃO"] <= f["DEADLINE_90"])

# --------------------------------------------------------
# TABELA RESUMIDA
# --------------------------------------------------------
tabela = (
    f.groupby(["ANO_ENTRADA", "MES_ENTRADA"])
    .agg(
        Entradas=("ENTRADA", "count"),
        Realizou30=("REALIZOU_30", "sum"),
        Perc30=("REALIZOU_30", lambda x: round((x.sum() / len(x)) * 100, 2)),
        Finalizou90=("FINALIZOU_90", "sum"),
        Perc90=("FINALIZOU_90", lambda x: round((x.sum() / len(x)) * 100, 2)),
    )
    .reset_index()
)

tabela["Mês"] = tabela["MES_ENTRADA"].apply(lambda m: NOME_MESES.get(int(m), m))
tabela = tabela.sort_values(["ANO_ENTRADA", "MES_ENTRADA"], ascending=[False, True])

tabela = tabela[
    ["ANO_ENTRADA", "Mês", "Entradas", "Realizou30", "Perc30", "Finalizou90", "Perc90"]
]

tabela.columns = [
    "Ano",
    "Mês",
    "Entradas",
    "Realizou a inspeção em até 30 dias",
    "% Realizou 30 dias",
    "Finalizou o processo em até 90 dias",
    "% Finalizou 90 dias",
]

st.subheader("📊 Tabela de Indicadores por Mês")
st.dataframe(tabela, use_container_width=True)

# --------------------------------------------------------
# KPIs
# --------------------------------------------------------
total = len(f)
tot_r30 = int(f["REALIZOU_30"].sum())
tot_f90 = int(f["FINALIZOU_90"].sum())

pct_r30 = round((tot_r30 / total) * 100, 2) if total else 0
pct_f90 = round((tot_f90 / total) * 100, 2) if total else 0

col1, col2, col3 = st.columns(3)
col1.metric("Entradas (período)", total)
col2.metric("Realizou a inspeção em até 30 dias (%)", f"{pct_r30}%")
col3.metric("Finalizou o processo em até 90 dias (%)", f"{pct_f90}%")

# --------------------------------------------------------
# ÁREA ADMIN
# --------------------------------------------------------
if is_admin:
    st.subheader("📈 Gráficos por Coordenação e Território")

    if col_coord:
        g = f.groupby(col_coord).agg(
            Entradas=("ENTRADA", "count"),
            Realizou_30=("REALIZOU_30", "sum"),
            Finalizou_90=("FINALIZOU_90", "sum"),
        ).reset_index()

        fig = px.bar(
            g,
            x=col_coord,
            y=["Realizou_30", "Finalizou_90"],
            title="Coordenação — Cumprimento (30d/90d)",
        )
        st.plotly_chart(fig, use_container_width=True)

    if col_territorio:
        g = f.groupby(col_territorio).agg(
            Entradas=("ENTRADA", "count"),
            Realizou_30=("REALIZOU_30", "sum"),
            Finalizou_90=("FINALIZOU_90", "sum"),
        ).reset_index()

        fig = px.bar(
            g,
            x=col_territorio,
            y=["Realizou_30", "Finalizou_90"],
            title="Território — Cumprimento (30d/90d)",
        )
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("⚠ Processos com atraso")

    atraso_30 = f[f["REALIZOU_30"] == False]
    atraso_90 = f[f["FINALIZOU_90"] == False]

    st.markdown("### 🔸 Atraso na primeira inspeção")
    st.dataframe(atraso_30, use_container_width=True)

    st.markdown("### 🔸 Atraso na conclusão")
    st.dataframe(atraso_90, use_container_width=True)

    dfs_export = {
        "Dados_Filtrados": f,
        "Resumo_Indicadores": tabela,
    }

    st.download_button(
        label="📥 Baixar relatório (Excel)",
        data=gerar_excel_bytes(dfs_export),
        file_name="relatorio_visa.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

else:
    st.info("Perfil padrão — visualização simplificada.")

st.caption(f"Usuário: {st.session_state['user']} | Perfil: {st.session_state['role'].upper()}")
