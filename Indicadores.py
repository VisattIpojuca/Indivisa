# painel_visa.py
# Painel VISA Ipojuca — Versão final (arquivo web)
# Requisitos: streamlit, pandas, plotly, xlsxwriter

import streamlit as st
import pandas as pd
from io import BytesIO
from datetime import timedelta
import plotly.express as px

# --------------------------------------------------------
# CONFIGURAÇÃO DA PÁGINA
# --------------------------------------------------------
st.set_page_config(page_title="Painel VISA Ipojuca - Com Login", layout="wide")
st.title("📊 Painel de Produção – Vigilância Sanitária de Ipojuca")

# --------------------------------------------------------
# FONTE DE DADOS: GOOGLE SHEETS
# --------------------------------------------------------
GOOGLE_SHEETS_URL = "https://docs.google.com/spreadsheets/d/1zsM8Zxdc-MnXSvV_OvOXiPoc1U4j-FOn/edit?usp=sharing"

def carregar_planilha_google():
    """Carrega a primeira aba da planilha do Google Sheets como CSV."""
    try:
        df = pd.read_csv(GOOGLE_SHEETS_URL)
    except Exception as e:
        st.error(f"Erro ao carregar Google Sheets: {e}")
        return pd.DataFrame()

    # Normaliza nomes
    df.columns = [str(c).strip() for c in df.columns]

    # Converte datas
    for col in ["ENTRADA", "1ª INSPEÇÃO", "DATA CONCLUSÃO"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], dayfirst=True, errors="coerce")

    # Ano/mês
    if "ENTRADA" in df.columns:
        df["ANO_ENTRADA"] = df["ENTRADA"].dt.year
        df["MES_ENTRADA"] = df["ENTRADA"].dt.month
    else:
        df["ANO_ENTRADA"] = pd.NA
        df["MES_ENTRADA"] = pd.NA

    # Normalização textos
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
# USUÁRIOS FIXOS E PERMISSÕES
# --------------------------------------------------------
USERS = {
    "admin": {"password": "Ipojuca@2025*", "role": "admin"},
    "antonio.reldismar": {"password": "Visa@2025", "role": "standard"}
}

# --------------------------------------------------------
# HELPERS
# --------------------------------------------------------
def converter_para_csv(url):
    partes = url.split("/d/")
    if len(partes) < 2:
        return None
    resto = partes[1]
    sheet_id = resto.split("/")[0]
    return f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"

@st.cache_data(ttl=600)
def carregar_planilha_google(url_original):
    url_csv = converter_para_csv(url_original)
    if not url_csv:
        return pd.DataFrame()
    try:
        df = pd.read_csv(url_csv)
    except Exception as e:
        st.error(f"Erro ao carregar planilha Google Sheets: {e}")
        return pd.DataFrame()
    df.columns = [c.strip() for c in df.columns]

    # converte datas (se existirem)
    for col in ["ENTRADA", "1ª INSPEÇÃO", "DATA CONCLUSÃO"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], dayfirst=True, errors="coerce")

    # ano/mês de entrada
    df["ANO_ENTRADA"] = df["ENTRADA"].dt.year
    df["MES_ENTRADA"] = df["ENTRADA"].dt.month

    # normaliza textos úteis
    if "SITUAÇÃO" in df.columns:
        df["SITUAÇÃO"] = df["SITUAÇÃO"].fillna("").astype(str).str.upper()
    if "CLASSIFICAÇÃO" in df.columns:
        df["CLASSIFICAÇÃO"] = df["CLASSIFICAÇÃO"].fillna("").astype(str).str.title()

    return df

def detectar_coluna(df, candidatos):
    """Retorna o primeiro nome de coluna presente em df de uma lista de candidatos."""
    for c in candidatos:
        if c in df.columns:
            return c
    return None

def gerar_excel_bytes(dfs_dict):
    out = BytesIO()
    with pd.ExcelWriter(out, engine="xlsxwriter") as writer:
        for nome, dfx in dfs_dict.items():
            try:
                dfx.to_excel(writer, sheet_name=nome[:31], index=False)
            except Exception:
                # se houver problemas com nome de sheet muito longo, usa nome curto
                dfx.to_excel(writer, sheet_name=nome[:31], index=False)
    return out.getvalue()

# -----------------------
# Carrega dados
# -----------------------
df = carregar_planilha_google(GSHEET_URL)
if df.empty:
    st.error("Nenhum dado encontrado. Verifique a planilha/URL.")
    st.stop()

# -----------------------
# Detecta colunas de coordenação/território (vários possíveis nomes)
# -----------------------
col_coord = detectar_coluna(df, ["COORDENAÇÃO", "COORDENACAO", "COORDENADORIA", "COORD"])
col_territorio = detectar_coluna(df, ["TERRITÓRIO", "TERRITORIO", "TERRITORY", "TERR"])

# -----------------------
# PERFIL DEFAULT: admin (visualização restrita sem login)
# - Por especificação: perfil administrativo não exige senha para ver o painel,
#   mas para ver as telas de atraso é necessário fazer login.
# -----------------------
if "role" not in st.session_state:
    st.session_state["role"] = "admin_view"  # pode ver painel, mas sem seções de atraso
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

# -----------------------
# Sidebar: filtros
# -----------------------
st.sidebar.header("Filtros")

modo = st.sidebar.radio("Período por:", ["Ano/Mês", "Intervalo de datas"])

NOME_MESES = {
    1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril",
    5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto",
    9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro"
}

if modo == "Ano/Mês":
    anos = sorted(df["ANO_ENTRADA"].dropna().unique())
    if not anos:
        st.error("Não há anos disponíveis nos dados.")
        st.stop()
    ano_sel = st.sidebar.selectbox("Ano", anos)

    meses_disp = sorted(df[df["ANO_ENTRADA"] == ano_sel]["MES_ENTRADA"].dropna().unique())
    mes_sel = st.sidebar.multiselect(
        "Mês",
        options=meses_disp,
        default=meses_disp,
        format_func=lambda m: NOME_MESES.get(int(m), str(int(m)))
    )
    df_filtrado = df[(df["ANO_ENTRADA"] == ano_sel) & (df["MES_ENTRADA"].isin(mes_sel))]
else:
    inicio = st.sidebar.date_input("Início", df["ENTRADA"].min().date())
    fim = st.sidebar.date_input("Fim", df["ENTRADA"].max().date())
    df_filtrado = df[(df["ENTRADA"].dt.date >= inicio) & (df["ENTRADA"].dt.date <= fim)]

# filtros opcionais
if col_territorio:
    territorios = sorted(df[col_territorio].dropna().unique())
    sel_ter = st.sidebar.multiselect("Território", options=territorios, default=territorios)
    if sel_ter:
        df_filtrado = df_filtrado[df_filtrado[col_territorio].isin(sel_ter)]

if "CLASSIFICAÇÃO" in df.columns:
    riscos = sorted(df["CLASSIFICAÇÃO"].dropna().unique())
    sel_risco = st.sidebar.multiselect("Classificação (Risco)", options=riscos, default=riscos)
    if sel_risco:
        df_filtrado = df_filtrado[df_filtrado["CLASSIFICAÇÃO"].isin(sel_risco)]

# --------------------------------------------------------
# LOGIN BLOQUEADOR (TELA INICIAL)
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

# Se não logado, mostra a página de login e bloqueia o resto
if not st.session_state["logged"]:
    st.title("🔐 Painel VISA Ipojuca — Acesso")
    st.markdown("Faça login para acessar o painel.")
    with st.form("login_form"):
        user_input = st.text_input("Usuário")
        pass_input = st.text_input("Senha", type="password")
        submitted = st.form_submit_button("Entrar")
        if submitted:
            ok = do_login(user_input, pass_input)
            if not ok:
                st.error("Usuário ou senha incorretos.")
    st.stop()

# --------------------------------------------------------
# CARREGA DADOS (arquivo local)
# --------------------------------------------------------
df = carregar_planilha_local()
if df.empty:
    st.error("Fonte de dados vazia. Verifique o arquivo local em /mnt/data.")
    st.stop()

# --------------------------------------------------------
# PAPEL DO USUÁRIO
# --------------------------------------------------------
is_admin = st.session_state["role"] == "admin"
is_standard = st.session_state["role"] == "standard"

# --------------------------------------------------------
# MAPA DE MESES E ANO PADRÃO
# --------------------------------------------------------
NOME_MESES = {
    1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril",
    5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto",
    9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro"
}
ANO_ATUAL = datetime.now().year

# --------------------------------------------------------
# SIDEBAR: FILTROS (visíveis conforme perfil)
# --------------------------------------------------------
st.sidebar.header(f"Olá, {st.session_state['user']} ({st.session_state['role']})")

modo = st.sidebar.radio("Período por:", ["Ano/Mês", "Intervalo de datas"])

# Anos disponíveis — pré-selecionar ano atual se houver
anos_disponiveis = sorted(df["ANO_ENTRADA"].dropna().unique())
if len(anos_disponiveis) == 0:
    anos_disponiveis = [ANO_ATUAL]

default_ano = ANO_ATUAL if ANO_ATUAL in anos_disponiveis else max(anos_disponiveis)

if modo == "Ano/Mês":
    ano_sel = st.sidebar.selectbox("Ano", anos_disponiveis, index=anos_disponiveis.index(default_ano))
    meses_disponiveis = sorted(df[df["ANO_ENTRADA"] == ano_sel]["MES_ENTRADA"].dropna().unique())
    mes_sel = st.sidebar.multiselect(
        "Mês",
        options=meses_disponiveis,
        default=meses_disponiveis,
        format_func=lambda m: NOME_MESES.get(int(m), str(m))
    )
else:
    inicio = st.sidebar.date_input("Data início", df["ENTRADA"].min().date())
    fim = st.sidebar.date_input("Data fim", df["ENTRADA"].max().date())

# Classificação sempre visível
if "CLASSIFICAÇÃO" in df.columns:
    classificacoes = sorted(df["CLASSIFICAÇÃO"].dropna().unique())
else:
    classificacoes = []
sel_risco = st.sidebar.multiselect("Classificação (Risco)", options=classificacoes, default=classificacoes)

# Detecta colunas de Território e Coordenação (nomes variados)
col_territorio = next((c for c in df.columns if "TERR" in c.upper()), None)
col_coord = next((c for c in df.columns if "COORD" in c.upper()), None)

# Território/Coordenação só para admin
if is_admin and col_territorio:
    territorios = sorted(df[col_territorio].dropna().unique())
    sel_ter = st.sidebar.multiselect("Território", options=territorios, default=territorios)
else:
    sel_ter = []

if is_admin and col_coord:
    coords = sorted(df[col_coord].dropna().unique())
    sel_coord = st.sidebar.multiselect("Coordenação", options=coords, default=coords)
else:
    sel_coord = []

# Logout
if st.sidebar.button("Sair / Logout"):
    do_logout()

# --------------------------------------------------------
# APLICA FILTROS
# --------------------------------------------------------
filtro_df = df.copy()

# Período
if modo == "Ano/Mês":
    filtro_df = filtro_df[(filtro_df["ANO_ENTRADA"] == ano_sel) & (filtro_df["MES_ENTRADA"].isin(mes_sel))]
else:
    filtro_df = filtro_df[(filtro_df["ENTRADA"].dt.date >= inicio) & (filtro_df["ENTRADA"].dt.date <= fim)]

# Classificação
if sel_risco:
    filtro_df = filtro_df[filtro_df["CLASSIFICAÇÃO"].isin(sel_risco)]

# Território/Coordenação (só admin)
if is_admin and sel_ter:
    filtro_df = filtro_df[filtro_df[col_territorio].isin(sel_ter)]
if is_admin and sel_coord:
    filtro_df = filtro_df[filtro_df[col_coord].isin(sel_coord)]

# --------------------------------------------------------
# CÁLCULO: deadlines e flags de cumprimento
# --------------------------------------------------------
filtro_df = filtro_df.copy()
filtro_df["DEADLINE_30"] = filtro_df["ENTRADA"] + timedelta(days=30)
filtro_df["DEADLINE_90"] = filtro_df["ENTRADA"] + timedelta(days=90)

filtro_df["REALIZOU_30"] = (filtro_df["1ª INSPEÇÃO"].notna()) & (filtro_df["1ª INSPEÇÃO"] <= filtro_df["DEADLINE_30"])
filtro_df["FINALIZOU_90"] = (filtro_df["DATA CONCLUSÃO"].notna()) & (filtro_df["DATA CONCLUSÃO"] <= filtro_df["DEADLINE_90"])

# --------------------------------------------------------
# TABELA RESUMIDA FORMATADA (ESTILO SOLICITADO)
# Agrupa por Ano/Mês e apresenta colunas no formato pedido
# --------------------------------------------------------
tabela = (
    filtro_df.groupby(["ANO_ENTRADA", "MES_ENTRADA"])
    .agg(
        Entradas=("ENTRADA", "count"),
        Realizou30=("REALIZOU_30", "sum"),
        Perc30=("REALIZOU_30", lambda x: round((x.sum() / len(x)) * 100, 2) if len(x) else 0),
        Finalizou90=("FINALIZOU_90", "sum"),
        Perc90=("FINALIZOU_90", lambda x: round((x.sum() / len(x)) * 100, 2) if len(x) else 0),
    )
    .reset_index()
)

# Muda mês numérico para nome
tabela["Mês"] = tabela["MES_ENTRADA"].apply(lambda m: NOME_MESES.get(int(m), m))

# Ordena por ano e mês (padrão)
tabela = tabela.sort_values(["ANO_ENTRADA", "MES_ENTRADA"], ascending=[False, True])

# Reordena e renomeia colunas conforme modelo
tabela = tabela[
    [
        "ANO_ENTRADA",
        "Mês",
        "Entradas",
        "Realizou30",
        "Perc30",
        "Finalizou90",
        "Perc90"
    ]
]

tabela.columns = [
    "Ano",
    "Mês",
    "Entradas",
    "Realizou a inspeção em até 30 dias",
    "% Realizou 30 dias",
    "Finalizou o processo em até 90 dias",
    "% Finalizou 90 dias"
]

# Exibe título e tabela
st.subheader("📊 Tabela de Indicadores por Mês")
st.dataframe(tabela, use_container_width=True)

# --------------------------------------------------------
# KPIs de topo (entradas totais e percentuais, visíveis para ambos)
# --------------------------------------------------------
total_entradas = len(filtro_df)
total_realizou = int(filtro_df["REALIZOU_30"].sum())
total_finalizou = int(filtro_df["FINALIZOU_90"].sum())

pct_realizou = round((total_realizou / total_entradas) * 100, 2) if total_entradas else 0.0
pct_finalizou = round((total_finalizou / total_entradas) * 100, 2) if total_entradas else 0.0

col1, col2, col3 = st.columns(3)
col1.metric("Entradas (período)", total_entradas)
col2.metric("Realizou a inspeção em até 30 dias (%)", f"{pct_realizou}%")
col3.metric("Finalizou o processo em até 90 dias (%)", f"{pct_finalizou}%")

# --------------------------------------------------------
# GRÁFICOS E SEÇÕES AVANÇADAS (APENAS ADMIN)
# --------------------------------------------------------
if is_admin:
    st.subheader("📈 Gráficos por Coordenação e Território")

    # Coordenação
    if col_coord:
        tmp = filtro_df.copy()
        coord_summary = tmp.groupby(col_coord).agg(
            Entradas=("ENTRADA", "count"),
            Realizou_30=("REALIZOU_30", "sum"),
            Finalizou_90=("FINALIZOU_90", "sum")
        ).reset_index().sort_values("Entradas", ascending=False)

        fig_coord = px.bar(
            coord_summary,
            x=col_coord,
            y=["Realizou_30", "Finalizou_90"],
            title="Coordenação: inspeções ≤30d e conclusões ≤90d",
            labels={col_coord: "Coordenação", "value": "Quantidade"}
        )
        st.plotly_chart(fig_coord, use_container_width=True)
    else:
        st.info("Coluna de Coordenação não encontrada — gráfico não exibido.")

    # Território
    if col_territorio:
        tmp = filtro_df.copy()
        ter_summary = tmp.groupby(col_territorio).agg(
            Entradas=("ENTRADA", "count"),
            Realizou_30=("REALIZOU_30", "sum"),
            Finalizou_90=("FINALIZOU_90", "sum")
        ).reset_index().sort_values("Entradas", ascending=False)

        fig_ter = px.bar(
            ter_summary,
            x=col_territorio,
            y=["Realizou_30", "Finalizou_90"],
            title="Território: inspeções ≤30d e conclusões ≤90d",
            labels={col_territorio: "Território", "value": "Quantidade"}
        )
        st.plotly_chart(fig_ter, use_container_width=True)
    else:
        st.info("Coluna de Território não encontrada — gráfico não exibido.")

    # Tabelas de atrasos
    st.subheader("⚠ Processos com atraso")

    atraso_30 = filtro_df[(filtro_df["REALIZOU_30"] == False)]
    atraso_90 = filtro_df[(filtro_df["FINALIZOU_90"] == False)]

    st.markdown("### 🔸 Atraso na primeira inspeção")
    st.dataframe(atraso_30, use_container_width=True)

    st.markdown("### 🔸 Atraso na conclusão")
    st.dataframe(atraso_90, use_container_width=True)

    # Download completo
    dfs_export = {
        "Dados_Filtrados": filtro_df,
        "Resumo_Indicadores": tabela
    }
    if col_coord:
        dfs_export["Resumo_Coordenação"] = coord_summary
    if col_territorio:
        dfs_export["Resumo_Território"] = ter_summary

    st.download_button(
        label="📥 Baixar relatório (Excel)",
        data=gerar_excel_bytes(dfs_export),
        file_name="relatorio_visa.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

else:
    st.info("Perfil padrão — visualização simplificada (sem gráficos/território/coordenação/atrasos).")

# --------------------------------------------------------
# FOOTER: usuário e papel
# --------------------------------------------------------
st.caption(f"Usuário: {st.session_state['user']} | Perfil: {st.session_state['role'].upper()}")
