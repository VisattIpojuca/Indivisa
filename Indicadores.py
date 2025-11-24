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
# Fonte de dados: arquivo local enviado (substitua se quiser usar Google Sheets)
# Nota: arquivo já carregado no ambiente: /mnt/data/PLANILHA REDESIM 2025 (Integrador).xlsx
DATA_PATH = "/mnt/data/PLANILHA REDESIM 2025 (Integrador).xlsx"
SHEET_NAME = "PLANILHA VISA"  # ajuste se for outra aba

# --------------------------------------------------------
# Usuários (fixos conforme solicitado)
USERS = {
    "admin": {
        "password": "Ipojuca@2025*",
        "role": "admin"  # vê tudo
    },
    "antonio.reldismar": {
        "password": "Visa@2025",
        "role": "standard"  # vê apenas indicadores e filtros reduzidos
    }
}

# --------------------------------------------------------
# Utilitários
# --------------------------------------------------------
def carregar_planilha_local(path=DATA_PATH, sheet=SHEET_NAME):
    """Carrega a planilha XLSX localmente e normaliza colunas/datas."""
    try:
        df = pd.read_excel(path, sheet_name=sheet)
    except Exception as e:
        st.error(f"Erro ao abrir arquivo local: {e}")
        return pd.DataFrame()

    # Normaliza nomes de colunas
    df.columns = [str(c).strip() for c in df.columns]

    # Converter datas com dayfirst (dia/mês/ano)
    for col in ["ENTRADA", "1ª INSPEÇÃO", "DATA CONCLUSÃO"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], dayfirst=True, errors="coerce")

    # Criar ano/mês a partir de ENTRADA
    df["ANO_ENTRADA"] = df["ENTRADA"].dt.year
    df["MES_ENTRADA"] = df["ENTRADA"].dt.month

    # Normaliza textos
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

# --- Se não autenticado, mostrar tela de login (bloqueadora) ---
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
# Usuário autenticado: carrega dados e mostra painel conforme papel
# --------------------------------------------------------
df = carregar_planilha_local()
if df.empty:
    st.error("Fonte de dados vazia. Verifique o arquivo local.")
    st.stop()

# --------------------------------------------------------
# Permissões e comportamento de UI
# - admin: vê tudo (filtros completos, gráficos, tabelas de atraso, download)
# - standard (antonio.reldismar): vê apenas indicadores, KPIs e filtros reduzidos
# --------------------------------------------------------
is_admin = st.session_state["role"] == "admin"
is_standard = st.session_state["role"] == "standard"

# --------------------------------------------------------
# Mapeamento meses e ano padrão (ano corrente pré-selecionado)
# --------------------------------------------------------
NOME_MESES = {
    1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril",
    5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto",
    9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro"
}
ANO_ATUAL = datetime.now().year

# --------------------------------------------------------
# Sidebar: filtros
# - padrão (standard): apenas Período e Classificação
# - admin: Período, Classificação, Território e Coordenação
# --------------------------------------------------------
st.sidebar.header(f"Olá, {st.session_state['user']} — filtros")

modo = st.sidebar.radio("Período por:", ["Ano/Mês", "Intervalo de datas"])

# Ano/Mês mode: usar anos da base, mas pré-selecionar para o ano corrente se existir
anos_disponiveis = sorted(df["ANO_ENTRADA"].dropna().unique())
if len(anos_disponiveis) == 0:
    anos_disponiveis = [ANO_ATUAL]

# Pre-seleção: se ano atual existe na base, selecionar; senão, selecionar maior disponível
default_ano = ANO_ATUAL if ANO_ATUAL in anos_disponiveis else max(anos_disponiveis)

if modo == "Ano/Mês":
    ano_sel = st.sidebar.selectbox("Ano", anos_disponiveis, index=anos_disponiveis.index(default_ano))
    meses_disp = sorted(df[df["ANO_ENTRADA"] == ano_sel]["MES_ENTRADA"].dropna().unique())
    # mostrar nomes dos meses, default para todos os meses disponíveis
    mes_sel = st.sidebar.multiselect(
        "Mês",
        options=meses_disp,
        default=meses_disp,
        format_func=lambda m: NOME_MESES.get(int(m), str(m))
    )
else:
    inicio = st.sidebar.date_input("Data início", value=df["ENTRADA"].min().date())
    fim = st.sidebar.date_input("Data fim", value=df["ENTRADA"].max().date())

# Classificação (disponível para ambos)
if "CLASSIFICAÇÃO" in df.columns:
    riscos = sorted(df["CLASSIFICAÇÃO"].dropna().unique())
    sel_risco = st.sidebar.multiselect("Classificação (Risco)", options=riscos, default=riscos)
else:
    sel_risco = []

# Território e Coordenação apenas para admin
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

# Logout
if st.sidebar.button("Sair / Logout"):
    do_logout()

# --------------------------------------------------------
# Aplica filtros
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

# Território e coordenação (apenas se admin e selecionados)
if is_admin and sel_ter:
    filtro_df = filtro_df[filtro_df[col_territorio].isin(sel_ter)]
if is_admin and sel_coord:
    filtro_df = filtro_df[filtro_df[col_coord].isin(sel_coord)]

# --------------------------------------------------------
# Cálculo de indicadores (numerador = entradas do período; denominador = cumpriram prazo)
# --------------------------------------------------------
def calcular_resumo(df_base, agrupar=True):
    df_tmp = df_base.copy()
    df_tmp["DEADLINE_30"] = df_tmp["ENTRADA"] + timedelta(days=30)
    df_tmp["DEADLINE_90"] = df_tmp["ENTRADA"] + timedelta(days=90)

    df_tmp["REALIZOU_30"] = (df_tmp["1ª INSPEÇÃO"].notna()) & (df_tmp["1ª INSPEÇÃO"] <= df_tmp["DEADLINE_30"])
    df_tmp["FINALIZOU_90"] = (df_tmp["DATA CONCLUSÃO"].notna()) & (df_tmp["DATA CONCLUSÃO"] <= df_tmp["DEADLINE_90"])

    if agrupar:
        rows = []
        grouped = df_tmp.groupby(["ANO_ENTRADA", "MES_ENTRADA"]) if ("ANO_ENTRADA" in df_tmp.columns and "MES_ENTRADA" in df_tmp.columns) else [("Total", "Total", df_tmp)]
        for (ano, mes), g in grouped:
            entradas = len(g)
            realizou = int(g["REALIZOU_30"].sum())
            finalizou = int(g["FINALIZOU_90"].sum())
            rows.append({
                "Ano": int(ano),
                "Mês": NOME_MESES.get(int(mes), mes) if isinstance(mes, (int, float)) else mes,
                "Entradas": entradas,
                "Realizou a inspeção em até 30 dias": realizou,
                "% Realizou 30 dias": round((realizou / entradas) * 100, 2) if entradas else 0.0,
                "Finalizou o processo em até 90 dias": finalizou,
                "% Finalizou 90 dias": round((finalizou / entradas) * 100, 2) if entradas else 0.0
            })
        return pd.DataFrame(rows).sort_values(["Ano", "Mês"])
    else:
        entradas = len(df_tmp)
        realizou = int(df_tmp["REALIZOU_30"].sum())
        finalizou = int(df_tmp["FINALIZOU_90"].sum())
        return pd.DataFrame([{
            "Entradas": entradas,
            "Realizou a inspeção em até 30 dias": realizou,
            "% Realizou 30 dias": round((realizou / entradas) * 100, 2) if entradas else 0.0,
            "Finalizou the processo em até 90 dias": finalizou,
            "% Finalizou 90 dias": round((finalizou / entradas) * 100, 2) if entradas else 0.0
        }])

agrupar = True if modo == "Ano/Mês" else False
df_ind = calcular_resumo(filtro_df, agrupar=agrupar)

# --------------------------------------------------------
# EXIBIÇÃO: Indicadores (visível para ambos)
# --------------------------------------------------------
st.header("📌 Indicadores do Período")
st.dataframe(df_ind, use_container_width=True)

# KPIs
if not df_ind.empty:
    if agrupar:
        ultima = df_ind.iloc[-1]
        col1, col2 = st.columns(2)
        col1.metric("Realizou a inspeção em até 30 dias (%)", f"{ultima['% Realizou 30 dias']}%")
        col2.metric("Finalizou o processo em até 90 dias (%)", f"{ultima['% Finalizou 90 dias']}%")
    else:
        linha = df_ind.iloc[0]
        col1, col2 = st.columns(2)
        col1.metric("Realizou a inspeção em até 30 dias (%)", f"{linha['% Realizou 30 dias']}%")
        col2.metric("Finalizou o processo em até 90 dias (%)", f"{linha['% Finalizou 90 dias']}%")

# --------------------------------------------------------
# Standard user: NÃO vê gráficos, territórios, coord, atrasos ou downloads
# Admin: vê gráficos por Coordenação e Território, se colunas existirem, e seções de atraso e download
# --------------------------------------------------------
if is_admin:
    st.header("📈 Gráficos por Coordenação e Território (Admin)")

    # Gráfico por Coordenação
    if col_coord:
        tmp = filtro_df.copy()
        tmp["REALIZOU_30"] = (tmp["1ª INSPEÇÃO"].notna()) & (tmp["1ª INSPEÇÃO"] <= (tmp["ENTRADA"] + timedelta(days=30)))
        tmp["FINALIZOU_90"] = (tmp["DATA CONCLUSÃO"].notna()) & (tmp["DATA CONCLUSÃO"] <= (tmp["ENTRADA"] + timedelta(days=90)))
        coord_summary = tmp.groupby(col_coord).agg(
            Entradas=("ENTRADA", "count"),
            Realizou_30=("REALIZOU_30", "sum"),
            Finalizou_90=("FINALIZOU_90", "sum")
        ).reset_index().sort_values("Entradas", ascending=False)

        fig = px.bar(coord_summary, x=col_coord, y=["Realizou_30", "Finalizou_90"],
                     labels={"value": "Quantidade", col_coord: col_coord},
                     title="Coordenação: inspeções ≤30d e conclusões ≤90d")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Coluna de Coordenação não encontrada — gráfico não exibido.")

    # Gráfico por Território
    if col_territorio:
        tmp = filtro_df.copy()
        tmp["REALIZOU_30"] = (tmp["1ª INSPEÇÃO"].notna()) & (tmp["1ª INSPEÇÃO"] <= (tmp["ENTRADA"] + timedelta(days=30)))
        tmp["FINALIZOU_90"] = (tmp["DATA CONCLUSÃO"].notna()) & (tmp["DATA CONCLUSÃO"] <= (tmp["ENTRADA"] + timedelta(days=90)))
        ter_summary = tmp.groupby(col_territorio).agg(
            Entradas=("ENTRADA", "count"),
            Realizou_30=("REALIZOU_30", "sum"),
            Finalizou_90=("FINALIZOU_90", "sum")
        ).reset_index().sort_values("Entradas", ascending=False)

        fig2 = px.bar(ter_summary, x=col_territorio, y=["Realizou_30", "Finalizou_90"],
                      labels={"value": "Quantidade", col_territorio: col_territorio},
                      title="Território: inspeções ≤30d e conclusões ≤90d")
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("Coluna de Território não encontrada — gráfico não exibido.")

    # Seções atrasadas
    st.header("⚠ Processos com atraso (Admin)")
    filtro_df["DEADLINE_30"] = filtro_df["ENTRADA"] + timedelta(days=30)
    filtro_df["DEADLINE_90"] = filtro_df["ENTRADA"] + timedelta(days=90)

    atraso_30 = filtro_df[(filtro_df["1ª INSPEÇÃO"].isna()) | (filtro_df["1ª INSPEÇÃO"] > filtro_df["DEADLINE_30"])]
    atraso_90 = filtro_df[(filtro_df["DATA CONCLUSÃO"].isna()) | (filtro_df["DATA CONCLUSÃO"] > filtro_df["DEADLINE_90"])]

    st.subheader("🔸 Atraso na primeira inspeção")
    st.dataframe(atraso_30, use_container_width=True)
    st.subheader("🔸 Atraso na conclusão")
    st.dataframe(atraso_90, use_container_width=True)

    # Download (admin)
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

# --------------------------------------------------------
# Fim do painel
# --------------------------------------------------------
st.caption(f"Usuário: {st.session_state['user']} | Perfil: {st.session_state['role'].upper()}")
