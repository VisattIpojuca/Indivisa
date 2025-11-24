# painel_final_com_login.py
import streamlit as st
import pandas as pd
from io import BytesIO
from datetime import datetime, timedelta
import plotly.express as px

# --------------------------------------------------------
# CONFIG
# --------------------------------------------------------
st.set_page_config(page_title="Painel VISA Ipojuca - Acesso Controlado", layout="wide")

# --------------------------------------------------------
# Fonte de dados: Google Sheets (primeira aba)
# --------------------------------------------------------
GOOGLE_SHEETS_URL = "https://docs.google.com/spreadsheets/d/1zsM8Zxdc-MnXSvV_OvOXiPoc1U4j-FOn/gviz/tq?tqx=out:csv"

def carregar_planilha_google():
    """Carrega a primeira aba da planilha Google Sheets como CSV."""
    try:
        df = pd.read_csv(GOOGLE_SHEETS_URL)
    except Exception as e:
        st.error(f"Erro ao carregar Google Sheets: {e}")
        return pd.DataFrame()

    # Normaliza nomes de colunas
    df.columns = [str(c).strip() for c in df.columns]

    # Converter datas
    for col in ["ENTRADA", "1ª INSPEÇÃO", "DATA CONCLUSÃO"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], dayfirst=True, errors="coerce")

    # Criar ano/mês
    if "ENTRADA" in df.columns:
        df["ANO_ENTRADA"] = df["ENTRADA"].dt.year
        df["MES_ENTRADA"] = df["ENTRADA"].dt.month
    else:
        df["ANO_ENTRADA"] = None
        df["MES_ENTRADA"] = None

    # Normalizar textos
    if "SITUAÇÃO" in df.columns:
        df["SITUAÇÃO"] = df["SITUAÇÃO"].fillna("").astype(str).str.upper()
    if "CLASSIFICAÇÃO" in df.columns:
        df["CLASSIFICAÇÃO"] = df["CLASSIFICAÇÃO"].fillna("").astype(str).str.title()

    return df

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
# Usuários (fixos conforme solicitado)
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

# --------------------------------------------------------
# Sessão: login inicial obrigatório
# --------------------------------------------------------
if "logged" not in st.session_state:
    st.session_state["logged"] = False
    st.session_state["user"] = None
    st.session_state["role"] = None

def do_login(username, password):
    if username in USERS and USERS[username]["password"] == password:
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

# Login
if not st.session_state["logged"]:
    st.title("🔐 Painel VISA Ipojuca — Login")
    st.markdown("Por favor faça login para acessar o painel.")
    with st.form("login_form"):
        username = st.text_input("Usuário")
        password = st.text_input("Senha", type="password")
        submitted = st.form_submit_button("Entrar")
        if submitted:
            ok = do_login(username.strip(), password)
            if not ok:
                st.error("Usuário ou senha incorretos.")
    st.stop()

# --------------------------------------------------------
# Carregamento dos dados (Google Sheets)
# --------------------------------------------------------
df = carregar_planilha_google()
if df.empty:
    st.error("⚠ Erro: Não foi possível carregar os dados do Google Sheets.")
    st.stop()

# --------------------------------------------------------
# Permissões
# --------------------------------------------------------
is_admin = st.session_state["role"] == "admin"
is_standard = st.session_state["role"] == "standard"

# --------------------------------------------------------
# Filtros
# --------------------------------------------------------
st.sidebar.header(f"Olá, {st.session_state['user']} — filtros")

NOME_MESES = {
    1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril",
    5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto",
    9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro"
}
ANO_ATUAL = datetime.now().year

modo = st.sidebar.radio("Período por:", ["Ano/Mês", "Intervalo de datas"])

anos_disponiveis = sorted(df["ANO_ENTRADA"].dropna().unique())
if len(anos_disponiveis) == 0:
    anos_disponiveis = [ANO_ATUAL]

default_ano = ANO_ATUAL if ANO_ATUAL in anos_disponiveis else max(anos_disponiveis)

if modo == "Ano/Mês":
    ano_sel = st.sidebar.selectbox("Ano", anos_disponiveis, index=anos_disponiveis.index(default_ano))
    meses_disp = sorted(df[df["ANO_ENTRADA"] == ano_sel]["MES_ENTRADA"].dropna().unique())
    mes_sel = st.sidebar.multiselect(
        "Mês",
        options=meses_disp,
        default=meses_disp,
        format_func=lambda m: NOME_MESES.get(int(m), str(m))
    )
else:
    inicio = st.sidebar.date_input("Data início", value=df["ENTRADA"].min().date())
    fim = st.sidebar.date_input("Data fim", value=df["ENTRADA"].max().date())

if "CLASSIFICAÇÃO" in df.columns:
    riscos = sorted(df["CLASSIFICAÇÃO"].dropna().unique())
    sel_risco = st.sidebar.multiselect("Classificação (Risco)", options=riscos, default=riscos)
else:
    sel_risco = []

# Território e coordenação (admin)
col_territorio = None
col_coord = None
for c in df.columns:
    if c.upper().startswith("TERR"):
        col_territorio = c
    if "COORD" in c.upper():
        col_coord = c

if is_admin:
    if col_territorio:
        territorios = sorted(df[col_territorio].dropna().unique())
        sel_ter = st.sidebar.multiselect("Território", options=territorios, default=territorios)
    else:
        sel_ter = []

    if col_coord:
        coords = sorted(df[col_coord].dropna().unique())
        sel_coord = st.sidebar.multiselect("Coordenação", options=coords, default=coords)
    else:
        sel_coord = []
else:
    sel_ter = []
    sel_coord = []

if st.sidebar.button("Sair / Logout"):
    do_logout()

# --------------------------------------------------------
# Aplicação dos filtros
# --------------------------------------------------------
filtro_df = df.copy()

if modo == "Ano/Mês":
    filtro_df = filtro_df[(filtro_df["ANO_ENTRADA"] == ano_sel) & (filtro_df["MES_ENTRADA"].isin(mes_sel))]
else:
    filtro_df = filtro_df[(filtro_df["ENTRADA"].dt.date >= inicio) & (filtro_df["ENTRADA"].dt.date <= fim)]

if sel_risco:
    filtro_df = filtro_df[filtro_df["CLASSIFICAÇÃO"].isin(sel_risco)]

if is_admin and sel_ter:
    filtro_df = filtro_df[filtro_df[col_territorio].isin(sel_ter)]
if is_admin and sel_coord:
    filtro_df = filtro_df[filtro_df[col_coord].isin(sel_coord)]

# --------------------------------------------------------
# Indicadores
# --------------------------------------------------------
def calcular_resumo(df_base, agrupar=True):
    df_tmp = df_base.copy()
    df_tmp["DEADLINE_30"] = df_tmp["ENTRADA"] + timedelta(days=30)
    df_tmp["DEADLINE_90"] = df_tmp["ENTRADA"] + timedelta(days=90)

    df_tmp["REALIZOU_30"] = (df_tmp["1ª INSPEÇÃO"].notna()) & (df_tmp["1ª INSPEÇÃO"] <= df_tmp["DEADLINE_30"])
    df_tmp["FINALIZOU_90"] = (df_tmp["DATA CONCLUSÃO"].notna()) & (df_tmp["DATA CONCLUSÃO"] <= df_tmp["DEADLINE_90"])

    if agrupar:
        rows = []
        grouped = df_tmp.groupby(["ANO_ENTRADA", "MES_ENTRADA"])
        for (ano, mes), g in grouped:
            entradas = len(g)
            realizou = int(g["REALIZOU_30"].sum())
            finalizou = int(g["FINALIZOU_90"].sum())
            rows.append({
                "Ano": int(ano),
                "Mês": NOME_MESES.get(int(mes), mes),
                "Entradas": entradas,
                "Realizou a inspeção em até 30 dias": realizou,
                "% Realizou 30 dias": round((realizou / entradas) * 100, 2) if entradas else 0.0,
                "Finalizou o processo em até 90 dias": finalizou,
                "% Finalizou 90 dias": round((finalizou / entradas) * 100, 2) if entradas else 0.0
            })
        return pd.DataFrame(rows)
    else:
        entradas = len(df_tmp)
        realizou = int(df_tmp["REALIZOU_30"].sum())
        finalizou = int(df_tmp["FINALIZOU_90"].sum())
        return pd.DataFrame([{
            "Entradas": entradas,
            "Realizou a inspeção em até 30 dias": realizou,
            "% Realizou 30 dias": round((realizou / entradas) * 100, 2) if entradas else 0.0,
            "Finalizou o processo em até 90 dias": finalizou,
            "% Finalizou 90 dias": round((finalizou / entradas) * 100, 2) if entradas else 0.0
        }])

agrupar = True if modo == "Ano/Mês" else False
df_ind = calcular_resumo(filtro_df, agrupar=agrupar)

# Indicadores
st.header("📌 Indicadores do Período")
st.dataframe(df_ind, use_container_width=True)

# KPIs
if not df_ind.empty:
    ultima = df_ind.iloc[-1]
    col1, col2 = st.columns(2)
    col1.metric("Realizou a inspeção em até 30 dias (%)", f"{ultima['% Realizou 30 dias']}%")
    col2.metric("Finalizou o processo em até 90 dias (%)", f"{ultima['% Finalizou 90 dias']}%")

# Gráficos e atrasos — apenas admin
if is_admin:
    st.header("📈 Gráficos por Coordenação e Território (Admin)")

    tmp = filtro_df.copy()
    tmp["REALIZOU_30"] = (tmp["1ª INSPEÇÃO"].notna()) & (tmp["1ª INSPEÇÃO"] <= (tmp["ENTRADA"] + timedelta(days=30)))
    tmp["FINALIZOU_90"] = (tmp["DATA CONCLUSÃO"].notna()) & (tmp["DATA CONCLUSÃO"] <= (tmp["ENTRADA"] + timedelta(days=90)))

    if col_coord:
        coord_summary = tmp.groupby(col_coord).agg(
            Entradas=("ENTRADA", "count"),
            Realizou_30=("REALIZOU_30", "sum"),
            Finalizou_90=("FINALIZOU_90", "sum")
        ).reset_index()

        fig = px.bar(coord_summary, x=col_coord, y=["Realizou_30", "Finalizou_90"],
                     title="Coordenação: inspeções ≤30d e conclusões ≤90d")
        st.plotly_chart(fig, use_container_width=True)

    if col_territorio:
        ter_summary = tmp.groupby(col_territorio).agg(
            Entradas=("ENTRADA", "count"),
            Realizou_30=("REALIZOU_30", "sum"),
            Finalizou_90=("FINALIZOU_90", "sum")
        ).reset_index()

        fig2 = px.bar(ter_summary, x=col_territorio, y=["Realizou_30", "Finalizou_90"],
                      title="Território: inspeções ≤30d e conclusões ≤90d")
        st.plotly_chart(fig2, use_container_width=True)

    st.header("⚠ Processos com atraso")
    filtro_df["DEADLINE_30"] = filtro_df["ENTRADA"] + timedelta(days=30)
    filtro_df["DEADLINE_90"] = filtro_df["ENTRADA"] + timedelta(days=90)

    atraso_30 = filtro_df[(filtro_df["1ª INSPEÇÃO"].isna()) | (filtro_df["1ª INSPEÇÃO"] > filtro_df["DEADLINE_30"])]
    atraso_90 = filtro_df[(filtro_df["DATA CONCLUSÃO"].isna()) | (filtro_df["DATA CONCLUSÃO"] > filtro_df["DEADLINE_90"])]

    st.subheader("🔸 Atraso na primeira inspeção")
    st.dataframe(atraso_30, use_container_width=True)

    st.subheader("🔸 Atraso na conclusão")
    st.dataframe(atraso_90, use_container_width=True)

    # Download
    dfs_export = {
        "Dados_Filtrados": filtro_df,
        "Resumo_Indicadores": df_ind
    }
    if col_coord:
        dfs_export["Resumo_Coordenação"] = coord_summary
    if col_territorio:
        dfs_export["Resumo_Território"] = ter_summary

    st.download_button(
        label="📥 Baixar relatório completo (Excel)",
        data=gerar_excel_bytes(dfs_export),
        file_name="relatorio_visa_admin.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

else:
    st.info("Você está no perfil padrão — acesso restrito às visualizações básicas.")

st.caption(f"Usuário: {st.session_state['user']} | Perfil: {st.session_state['role'].upper()}")
