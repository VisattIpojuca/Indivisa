# painel_com_login.py
import streamlit as st
import pandas as pd
from io import BytesIO
from datetime import timedelta
import plotly.express as px

# -----------------------
# Configuração da página
# -----------------------
st.set_page_config(page_title="Painel VISA Ipojuca - Com Login", layout="wide")
st.title("📊 Painel de Produção – Vigilância Sanitária de Ipojuca")

# -----------------------
# Link da planilha Google
# (ou substitua por um caminho local se preferir)
# -----------------------
GSHEET_URL = "https://docs.google.com/spreadsheets/d/1zsM8Zxdc-MnXSvV_OvOXiPoc1U4j-FOn/edit?usp=sharing"

# -----------------------
# Helpers
# -----------------------
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

# -----------------------
# Área de login (ABAIXO dos filtros, conforme solicitado)
# -----------------------
st.sidebar.markdown("---")
st.sidebar.markdown("### Login (para ver telas de atraso)")

with st.sidebar.form("login_form", clear_on_submit=False):
    username = st.text_input("Usuário")
    password = st.text_input("Senha", type="password")
    submitted = st.form_submit_button("Entrar")
    if submitted:
        # Credenciais solicitadas
        if username == "admin" and password == "Ipojuca@2025*":
            st.session_state["authenticated"] = True
            st.session_state["role"] = "admin_full"
            st.experimental_rerun()
        else:
            st.error("Usuário ou senha incorretos.")

# Botão para "visualização administrativa" que não exige senha (o default já é admin_view),
# mas deixamos um botão para garantir o modo:
if st.sidebar.button("Entrar como visualizador administrativo (sem login)"):
    st.session_state["authenticated"] = False
    st.session_state["role"] = "admin_view"
    st.experimental_rerun()

# Botão logout (quando autenticado)
if st.session_state.get("authenticated"):
    if st.sidebar.button("Sair (logout)"):
        st.session_state["authenticated"] = False
        st.session_state["role"] = "admin_view"
        st.experimental_rerun()

# -----------------------
# Cálculo dos indicadores (seguindo especificação)
# - Numerador = todas as entradas do período (já é a base filtrada)
# - Denominador = apenas os que cumpriram prazo
# -----------------------
def calcular_indicadores(df_base, agrupar=True):
    df_tmp = df_base.copy()
    df_tmp["DEADLINE_30"] = df_tmp["ENTRADA"] + timedelta(days=30)
    df_tmp["DEADLINE_90"] = df_tmp["ENTRADA"] + timedelta(days=90)

    df_tmp["REALIZOU_30"] = (df_tmp["1ª INSPEÇÃO"].notna()) & (df_tmp["1ª INSPEÇÃO"] <= df_tmp["DEADLINE_30"])
    df_tmp["FINALIZOU_90"] = (df_tmp["DATA CONCLUSÃO"].notna()) & (df_tmp["DATA CONCLUSÃO"] <= df_tmp["DEADLINE_90"])

    if agrupar:
        rows = []
        for (ano, mes), g in df_tmp.groupby(["ANO_ENTRADA", "MES_ENTRADA"]):
            entradas = len(g)
            realizou_30 = int(g["REALIZOU_30"].sum())
            finalizou_90 = int(g["FINALIZOU_90"].sum())
            rows.append({
                "Ano": int(ano),
                "Mês": NOME_MESES.get(int(mes), int(mes)),
                "Entradas": entradas,
                "Realizou a inspeção em até 30 dias": realizou_30,
                "% Realizou 30 dias": round((realizou_30 / entradas) * 100, 2) if entradas else 0.0,
                "Finalizou o processo em até 90 dias": finalizou_90,
                "% Finalizou 90 dias": round((finalizou_90 / entradas) * 100, 2) if entradas else 0.0,
            })
        return pd.DataFrame(rows).sort_values(["Ano", "Mês"])
    else:
        entradas = len(df_tmp)
        realizou_30 = int(df_tmp["REALIZOU_30"].sum())
        finalizou_90 = int(df_tmp["FINALIZOU_90"].sum())
        return pd.DataFrame([{
            "Entradas": entradas,
            "Realizou a inspeção em até 30 dias": realizou_30,
            "% Realizou 30 dias": round((realizou_30 / entradas) * 100, 2) if entradas else 0.0,
            "Finalizou o processo em até 90 dias": finalizou_90,
            "% Finalizou 90 dias": round((finalizou_90 / entradas) * 100, 2) if entradas else 0.0,
        }])

agrupar = True if modo == "Ano/Mês" else False
df_ind = calcular_indicadores(df_filtrado, agrupar=agrupar)

# -----------------------
# Exibição principal
# -----------------------
st.subheader("📌 Indicadores do período")
st.dataframe(df_ind, use_container_width=True)

# KPIs principais (último período/total)
if not df_ind.empty:
    if agrupar:
        ultima = df_ind.iloc[-1]
        st.metric("Realizou a inspeção em até 30 dias (%)", f"{ultima['% Realizou 30 dias']}%")
        st.metric("Finalizou o processo em até 90 dias (%)", f"{ultima['% Finalizou 90 dias']}%")
    else:
        linha = df_ind.iloc[0]
        st.metric("Realizou a inspeção em até 30 dias (%)", f"{linha['% Realizou 30 dias']}%")
        st.metric("Finalizou o processo em até 90 dias (%)", f"{linha['% Finalizou 90 dias']}%")

# -----------------------
# GRAFICOS: por Coordenação e por Território
# -----------------------
st.subheader("📈 Gráficos agregados")

# Agregação por coordenação (se existir)
if col_coord and col_coord in df_filtrado.columns:
    grp_coord = df_filtrado.copy()
    grp_coord["REALIZOU_30"] = (grp_coord["1ª INSPEÇÃO"].notna()) & (grp_coord["1ª INSPEÇÃO"] <= (grp_coord["ENTRADA"] + timedelta(days=30)))
    grp_coord["FINALIZOU_90"] = (grp_coord["DATA CONCLUSÃO"].notna()) & (grp_coord["DATA CONCLUSÃO"] <= (grp_coord["ENTRADA"] + timedelta(days=90)))

    coord_summary = grp_coord.groupby(col_coord).agg(
        Entradas=("ENTRADA", "count"),
        Realizou_30=("REALIZOU_30", "sum"),
        Finalizou_90=("FINALIZOU_90", "sum")
    ).reset_index()

    # gráfico empilhado / barras lado a lado
    fig_coord = px.bar(
        coord_summary.sort_values("Entradas", ascending=False),
        x=col_coord,
        y=["Realizou_30", "Finalizou_90"],
        labels={"value": "Quantidade", col_coord: col_coord},
        title=f"Coordenação: quantidade de inspeções (≤30d) e conclusões (≤90d) — período selecionado"
    )
    st.plotly_chart(fig_coord, use_container_width=True)
else:
    st.info("Coluna de Coordenação não encontrada na planilha — pulando gráfico por coordenação.")

# Agregação por território (se existir)
if col_territorio and col_territorio in df_filtrado.columns:
    grp_ter = df_filtrado.copy()
    grp_ter["REALIZOU_30"] = (grp_ter["1ª INSPEÇÃO"].notna()) & (grp_ter["1ª INSPEÇÃO"] <= (grp_ter["ENTRADA"] + timedelta(days=30)))
    grp_ter["FINALIZOU_90"] = (grp_ter["DATA CONCLUSÃO"].notna()) & (grp_ter["DATA CONCLUSÃO"] <= (grp_ter["ENTRADA"] + timedelta(days=90)))

    ter_summary = grp_ter.groupby(col_territorio).agg(
        Entradas=("ENTRADA", "count"),
        Realizou_30=("REALIZOU_30", "sum"),
        Finalizou_90=("FINALIZOU_90", "sum")
    ).reset_index()

    fig_ter = px.bar(
        ter_summary.sort_values("Entradas", ascending=False),
        x=col_territorio,
        y=["Realizou_30", "Finalizou_90"],
        labels={"value": "Quantidade", col_territorio: col_territorio},
        title=f"Território: quantidade de inspeções (≤30d) e conclusões (≤90d) — período selecionado"
    )
    st.plotly_chart(fig_ter, use_container_width=True)
else:
    st.info("Coluna de Território não encontrada na planilha — pulando gráfico por território.")

# -----------------------
# SEÇÕES DE ATRASOS (MOSTRADAS SOMENTE SE USUÁRIO AUTENTICADO)
# -----------------------
if st.session_state.get("authenticated"):
    st.subheader("⚠ Processos com atraso (visível apenas após login autenticado)")

    df_filtrado["DEADLINE_30"] = df_filtrado["ENTRADA"] + timedelta(days=30)
    df_filtrado["DEADLINE_90"] = df_filtrado["ENTRADA"] + timedelta(days=90)

    atraso_30 = df_filtrado[(df_filtrado["1ª INSPEÇÃO"].isna()) | (df_filtrado["1ª INSPEÇÃO"] > df_filtrado["DEADLINE_30"])]
    atraso_90 = df_filtrado[(df_filtrado["DATA CONCLUSÃO"].isna()) | (df_filtrado["DATA CONCLUSÃO"] > df_filtrado["DEADLINE_90"])]

    st.markdown("### 🔸 Atraso na primeira inspeção")
    st.dataframe(atraso_30, use_container_width=True)

    st.markdown("### 🔸 Atraso na conclusão")
    st.dataframe(atraso_90, use_container_width=True)
else:
    st.info("Seção de processos com atraso oculta. Faça login para acessar informações detalhadas.")

# -----------------------
# DOWNLOAD: adiciona resumos por coordenação e território
# -----------------------
# prepara agregações extras
coord_summary = pd.DataFrame()
ter_summary = pd.DataFrame()
if col_coord and col_coord in df_filtrado.columns:
    coord_summary = df_filtrado.groupby(col_coord).agg(
        Entradas=("ENTRADA", "count"),
        Realizou_30=("1ª INSPEÇÃO", lambda s: ((pd.to_datetime(s.notna()) & (df_filtrado.loc[s.index, "1ª INSPEÇÃO"] <= (df_filtrado.loc[s.index, "ENTRADA"] + timedelta(days=30))))).sum() if True else 0)
    ).reset_index()
    # safer compute
    coord_summary["Realizou_30"] = coord_summary[col_coord].apply(lambda x: int(((df_filtrado[col_coord]==x) & ((df_filtrado["1ª INSPEÇÃO"].notna()) & (df_filtrado["1ª INSPEÇÃO"] <= df_filtrado["ENTRADA"] + timedelta(days=30)))).sum()))
    coord_summary["Finalizou_90"] = coord_summary[col_coord].apply(lambda x: int(((df_filtrado[col_coord]==x) & ((df_filtrado["DATA CONCLUSÃO"].notna()) & (df_filtrado["DATA CONCLUSÃO"] <= df_filtrado["ENTRADA"] + timedelta(days=90)))).sum()))

if col_territorio and col_territorio in df_filtrado.columns:
    ter_summary = df_filtrado.groupby(col_territorio).agg(Entradas=("ENTRADA", "count")).reset_index()
    ter_summary["Realizou_30"] = ter_summary[col_territorio].apply(lambda x: int(((df_filtrado[col_territorio]==x) & ((df_filtrado["1ª INSPEÇÃO"].notna()) & (df_filtrado["1ª INSPEÇÃO"] <= df_filtrado["ENTRADA"] + timedelta(days=30)))).sum()))
    ter_summary["Finalizou_90"] = ter_summary[col_territorio].apply(lambda x: int(((df_filtrado[col_territorio]==x) & ((df_filtrado["DATA CONCLUSÃO"].notna()) & (df_filtrado["DATA CONCLUSÃO"] <= df_filtrado["ENTRADA"] + timedelta(days=90)))).sum()))

# prepara dfs para exportação
dfs_para_export = {
    "Dados_Filtrados": df_filtrado,
    "Resumo_Indicadores": df_ind
}
if not coord_summary.empty:
    dfs_para_export["Resumo_Coordenação"] = coord_summary
if not ter_summary.empty:
    dfs_para_export["Resumo_Território"] = ter_summary

st.download_button(
    label="📥 Baixar relatório (Excel)",
    data=gerar_excel_bytes(dfs_para_export),
    file_name="relatorio_visa_com_login.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)

st.caption("Painel com login — Vigilância Sanitária de Ipojuca")
