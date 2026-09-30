"""Hub de Indicadores — Central de Gente & Dados (Pacaembu Construtora).

Página única com todos os indicadores, agrupados por gerência e projeto. O conteúdo
vem de `indicadores.toml` — para incluir um indicador, edite só esse arquivo.
Sem login: é só uma página de links, e cada painel tem a própria senha.
Padrão visual dos painéis (skill padrao-painel-streamlit): cards `pp.kpi`, Nunito, fundo claro.
Versão anterior (antes do padrão visual, 30/09/2026): tag git `hub-v1-antes-padrao-visual`.

    streamlit run app.py
"""

from __future__ import annotations

import re
import tomllib
import unicodedata
from datetime import date, datetime, timedelta
from html import escape
from pathlib import Path
from zoneinfo import ZoneInfo

import psycopg2

import streamlit as st

import painel_padrao as pp

ROOT = Path(__file__).resolve().parent
CATALOGO = ROOT / "indicadores.toml"
FUSO = ZoneInfo("America/Sao_Paulo")
DIAS_NOVIDADE = 21  # o selo "Novidade" aparece por 3 semanas depois da data da mudança

# status do toml -> (rótulo, classe). "em construção" continua sendo o valor no toml (compatível).
STATUS = {
    "no ar": ("No ar", "noar"),
    "em construção": ("Em desenvolvimento", "construcao"),
}
FILTROS_STATUS = ["No ar", "Em desenvolvimento", "Pausado"]
TIPO_LINK = {
    "streamlit": ":material/open_in_new:",
    "databricks-app": ":material/open_in_new:",
    "dashboard": ":material/bar_chart:",
    "power-bi": ":material/insert_chart:",
    "documento": ":material/description:",
    "outro": ":material/link:",
}

# Paleta oficial Pacaembu Construtora: #064D66 (azul), #FAB900 (amarelo), #F02727 (vermelho),
# #003244 (azul escuro). Cada card tem uma faixa no topo com a cor do status.
CSS = """
<style>
[class*="st-key-card-"] {
  background: #FFFFFF;
  border-radius: 16px !important;
  border: 1px solid #DCE5EA !important;
  box-shadow: 0 1px 2px rgba(0, 50, 68, .06), 0 4px 14px rgba(0, 50, 68, .05);
  transition: transform .15s ease, box-shadow .15s ease;
  overflow: hidden;
  padding: 1.1rem 1.1rem 1rem !important;
}
[class*="st-key-card-"]:hover {
  transform: translateY(-2px);
  box-shadow: 0 2px 4px rgba(0, 50, 68, .08), 0 10px 24px rgba(0, 50, 68, .10);
}
[class*="st-key-card-noar"] { border-top: 4px solid #064D66 !important; }
[class*="st-key-card-construcao"] { border-top: 4px solid #FAB900 !important; }
[class*="st-key-card-pausado"] { border-top: 4px solid #B8C4CC !important; }
[class*="st-key-card-ideia"] { border-top: 4px solid #B8C4CC !important; }

.hub-intro { background: #FFFFFF; border: 1px solid #DCE5EA; border-left: 4px solid #FAB900; border-radius: 12px;
  padding: .9rem 1.1rem; color: #003244; font-size: .92rem; line-height: 1.5; height: 100%; box-sizing: border-box; }
.hub-intro b { color: #064D66; }
@media (max-width: 640px) { .hub-intro-mais { display: none; } }

.hub-head { display: flex; align-items: center; gap: .85rem; }
.hub-logo {
  flex: 0 0 56px; height: 56px; border-radius: 14px; background: #F3F6F8;
  display: flex; align-items: center; justify-content: center;
}
.hub-logo img { max-width: 40px; max-height: 40px; border-radius: 0; }
.hub-iniciais { color: #064D66; font-weight: 800; font-size: 1.05rem; letter-spacing: .02em; }
.hub-nome { font-weight: 800; font-size: 1.08rem; color: #003244; line-height: 1.2; }
.hub-selos { display: flex; flex-wrap: wrap; gap: .3rem; align-items: center; margin-top: .3rem; }
.hub-status {
  position: relative; display: inline-flex; align-items: center; gap: .35rem;
  font-size: .74rem; font-weight: 700; padding: .12rem .55rem; border-radius: 999px;
}
.hub-status::before { content: ""; width: .45rem; height: .45rem; border-radius: 50%; background: currentColor; }
.hub-status.noar { color: #0B6B45; background: #E5F4EC; }
.hub-status.construcao { color: #8A5B00; background: #FFF3D1; }
.hub-status.ideia, .hub-status.pausado { color: #5B6B75; background: #EEF2F4; }
.hub-status.novidade { color: #FFFFFF; background: #F02727; }
.hub-status.novidade::before { background: #FFFFFF; }
/* selos com explicação (Pausado, Novidade): balão ao passar o mouse ou tocar */
.hub-dica { cursor: help; outline: none; }
.hub-dica::after {
  content: attr(data-dica); position: absolute; top: calc(100% + 8px); right: 0; z-index: 20;
  width: max-content; max-width: 270px; white-space: normal; background: #003244; color: #FFFFFF;
  font-size: .76rem; font-weight: 500; line-height: 1.45; padding: .55rem .7rem; border-radius: 8px;
  box-shadow: 0 6px 18px rgba(0, 50, 68, .25); opacity: 0; visibility: hidden; transition: opacity .15s;
}
.hub-dica:hover::after, .hub-dica:focus::after { opacity: 1; visibility: visible; }
[class*="st-key-card-"]:has(.hub-dica:hover), [class*="st-key-card-"]:has(.hub-dica:focus) { overflow: visible; z-index: 5; }
.hub-desc { color: #4A5E69; font-size: .9rem; line-height: 1.45; margin: .85rem 0 .75rem; }
.hub-meta { background: #F5F8FA; border-radius: 10px; padding: .55rem .75rem; font-size: .8rem; }
.hub-meta div { display: flex; gap: .5rem; padding: .12rem 0; color: #003244; align-items: center; }
.hub-meta span.rot { flex: 0 0 6.6rem; color: #7A8C96; font-weight: 600; }
.hub-ponto { width: .55rem; height: .55rem; border-radius: 50%; display: inline-block; flex: 0 0 .55rem; }
.hub-erro { color: #C41E1E; font-weight: 700; }

/* gerências: bloco que abre e fecha, título no padrão das seções dos painéis */
[data-testid="stExpander"] details { background: transparent; border: none; border-bottom: 1px solid #DCE5EA; border-radius: 0; }
[data-testid="stExpander"] summary { padding: .55rem .1rem; }
[data-testid="stExpander"] summary p { color: #064D66; font-weight: 800; font-size: 1.12rem; }
[data-testid="stExpander"] summary:hover p { color: #003244; }
[data-testid="stExpander"] [data-testid="stExpanderDetails"] { padding: .2rem 0 1rem; }
/* celular: cards de resumo 2 por linha (o Streamlit empilha as colunas em telas estreitas) */
@media (max-width: 640px) {
  [data-testid="stHorizontalBlock"]:has(.pp-kpi) { flex-direction: row !important; flex-wrap: wrap !important; gap: .6rem !important; }
  [data-testid="stHorizontalBlock"]:has(.pp-kpi) > [data-testid="stColumn"] {
    flex: 1 1 calc(50% - .3rem) !important; width: calc(50% - .3rem) !important; min-width: calc(50% - .3rem) !important; }
  [data-testid="stHorizontalBlock"]:has(.pp-kpi) > [data-testid="stColumn"]:not(:has(.pp-kpi)) {
    flex: 1 1 100% !important; width: 100% !important; min-width: 100% !important; }
  .pp-kpi-valor { font-size: 1.45rem !important; }
}
.hub-rodape { color: #7A8C96; font-size: .82rem; text-align: center; padding: 1.2rem 0 .4rem; border-top: 1px solid #DCE5EA; margin-top: 1rem; }
.hub-rodape a { color: #064D66; font-weight: 700; }
</style>
"""


@st.cache_data(ttl=60)
def carregar_catalogo(mtime: float) -> dict:
    # mtime entra no cache: salvou o .toml, a página já relê.
    with CATALOGO.open("rb") as f:
        return tomllib.load(f)


@st.cache_data(ttl=300, show_spinner=False)
def _ler_cargas(url: str) -> dict[str, tuple[datetime, str]]:
    """{"schema.tabela": (concluido_em, status)} de ops.v_ultima_carga. Levanta exceção
    em caso de falha — assim o erro não fica guardado no cache e a próxima visita tenta de novo."""
    with psycopg2.connect(url, connect_timeout=5) as conn, conn.cursor() as cur:
        cur.execute("SELECT schema_nome || '.' || tabela, concluido_em, status FROM ops.v_ultima_carga")
        return {tabela: (quando, status) for tabela, quando, status in cur.fetchall()}


def ultimas_cargas() -> tuple[dict[str, tuple[datetime, str]], str | None]:
    """(cargas, motivo). Sem conexão devolve ({}, motivo) e os cards caem no texto de
    "atualizacao". O motivo nunca inclui a URL nem a senha."""
    try:
        url = st.secrets["neon_hub"]["database_url"]
    except Exception:  # noqa: BLE001 — secrets.toml ausente ou sem o bloco
        return {}, "o bloco [neon_hub] com database_url não foi encontrado nos Secrets"
    try:
        return _ler_cargas(url), None
    except psycopg2.OperationalError as exc:
        if "password authentication failed" in str(exc):
            return {}, "o Neon recusou a senha do usuário do Hub"
        return {}, "não foi possível conectar ao Neon"
    except Exception as exc:  # noqa: BLE001 — o Hub continua de pé sem o Neon
        return {}, f"erro ao ler as cargas ({type(exc).__name__})"


def atualizacao(projeto: dict, cargas: dict) -> tuple[str, str | None]:
    """(texto, situação): situação "hoje" (verde), "antiga" (amarelo), "erro" (vermelho) ou None
    (atualização mensal/texto fixo, sem ponto)."""
    registro = cargas.get(projeto.get("carga", ""))
    agora = datetime.now(FUSO)
    if not registro or registro[0] is None:
        diaria = projeto.get("atualizacao_diaria")
        if diaria:
            # atualização fixa todo dia nesse horário: hoje, se já passou; senão, ontem
            hora, minuto = (int(x) for x in diaria.split(":"))
            ultima = agora.replace(hour=hora, minute=minuto, second=0, microsecond=0)
            if agora < ultima:
                ultima -= timedelta(days=1)
            return ultima.strftime("%d/%m/%Y às %H:%M"), "hoje" if ultima.date() == agora.date() else "antiga"
        return escape(projeto.get("atualizacao", "")), None
    quando, status = registro
    local = quando.astimezone(FUSO)
    texto = local.strftime("%d/%m/%Y às %H:%M")
    if status != "ok":
        return texto + ' · <span class="hub-erro">erro na última carga</span>', "erro"
    return texto, "hoje" if local.date() == agora.date() else "antiga"


COR_SITUACAO = {"hoje": ("#16A34A", "Atualizado hoje"), "antiga": ("#FAB900", "Não atualizado hoje"),
                "erro": ("#F02727", "A última carga falhou")}


def pausado(projeto: dict) -> bool:
    return bool(projeto.get("pausado"))


def categoria(projeto: dict) -> str:
    """Rótulo do filtro de status: No ar, Em desenvolvimento ou Pausado."""
    if pausado(projeto):
        return "Pausado"
    return STATUS.get(projeto.get("status", ""), ("",))[0]


def novidade(projeto: dict) -> tuple[str, str] | None:
    """(data dd/mm, texto) se a última mudança do painel for recente (campos novidade / novidade_data)."""
    texto, quando = projeto.get("novidade"), projeto.get("novidade_data")
    if not texto or not quando:
        return None
    d = quando if isinstance(quando, date) else date.fromisoformat(str(quando))
    if (datetime.now(FUSO).date() - d).days > DIAS_NOVIDADE:
        return None
    return f"{d:%d/%m}", texto


def casa_busca(projeto: dict, gerencia: str, termo: str) -> bool:
    if not termo:
        return True
    texto = " ".join(str(projeto.get(k, "")) for k in ("nome", "descricao", "fonte", "novidade")) + " " + gerencia
    return termo.lower() in texto.lower()


def _slug(texto: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()).strip("-")


def _iniciais(nome: str) -> str:
    palavras = [p for p in re.split(r"\W+", nome) if p and p[0].isupper()] or nome.split()
    if len(palavras) == 1:
        return palavras[0][:2].upper()
    return "".join(p[0] for p in palavras[:2]).upper()


def cabecalho_card(projeto: dict, cargas: dict) -> str:
    rotulo, classe = STATUS.get(projeto.get("status", ""), ("Sem status", "ideia"))
    rotulo = projeto.get("rotulo_status", rotulo)
    selos = f'<span class="hub-status {classe}">{escape(rotulo)}</span>'
    if pausado(projeto):
        selos += (f'<span class="hub-status pausado hub-dica" tabindex="0" data-dica="{escape(projeto["pausado"])}" '
                  f'aria-label="{escape(projeto["pausado"])}">Pausado</span>')
    nov = novidade(projeto)
    if nov:
        dica = f"O que mudou em {nov[0]}: {nov[1]}"
        selos += (f'<span class="hub-status novidade hub-dica" tabindex="0" data-dica="{escape(dica)}" '
                  f'aria-label="{escape(dica)}">Novidade</span>')
    logo = projeto.get("logo")
    if logo and (ROOT / "static" / "logos" / logo).exists():
        tile = f'<div class="hub-logo"><img src="app/static/logos/{escape(logo)}" alt=""></div>'
    else:
        tile = f'<div class="hub-logo"><span class="hub-iniciais">{escape(_iniciais(projeto["nome"]))}</span></div>'
    texto_atu, situacao = atualizacao(projeto, cargas)
    ponto = ""
    if situacao:
        cor, dica = COR_SITUACAO[situacao]
        ponto = f'<span class="hub-ponto" style="background:{cor}" title="{dica}"></span>'
    meta = "".join(
        f'<div><span class="rot">{rot}</span>{valor}</div>'
        for rot, valor in (("Fonte", escape(projeto.get("fonte", ""))), ("Atualizado em", f"{ponto}{texto_atu}" if texto_atu else ""))
        if valor
    )
    return (
        f'<div class="hub-head">{tile}<div><div class="hub-nome">{escape(projeto["nome"])}</div>'
        f'<div class="hub-selos">{selos}</div></div></div>'
        f'<p class="hub-desc">{escape(projeto.get("descricao", ""))}</p>'
        + (f'<div class="hub-meta">{meta}</div>' if meta else "")
    )


def card_projeto(projeto: dict, cargas: dict) -> None:
    _, classe = STATUS.get(projeto.get("status", ""), ("", "ideia"))
    if pausado(projeto):
        classe = "pausado"
    with st.container(border=True, height="stretch", key=f"card-{classe}-{_slug(projeto['nome'])}"):
        st.html(cabecalho_card(projeto, cargas))
        links = projeto.get("link", [])
        if not links:
            return
        st.space("stretch")  # empurra os botões para o rodapé, alinhados entre cards
        with st.container(horizontal=True, gap="small"):
            for n, link in enumerate(links):
                icone_link = TIPO_LINK.get(link.get("tipo", "outro"), ":material/link:")
                if link.get("url"):
                    st.link_button(link["rotulo"], link["url"], icon=icone_link, type="primary" if n == 0 else "secondary")
                else:
                    st.button(f"{link['rotulo']} · link pendente", icon=":material/link_off:", disabled=True, key=f"{projeto['nome']}-{link['rotulo']}")


def resumo_gerencia(projetos: list[dict]) -> str:
    """ "2 no ar · 1 em desenvolvimento · 1 pausado" (só o que existe)."""
    cont = {c: sum(categoria(p) == c for p in projetos) for c in FILTROS_STATUS}
    partes = [f"{cont['No ar']} no ar" if cont["No ar"] else "",
              f"{cont['Em desenvolvimento']} em desenvolvimento" if cont["Em desenvolvimento"] else "",
              f"{cont['Pausado']} {'pausado' if cont['Pausado'] == 1 else 'pausados'}" if cont["Pausado"] else ""]
    return " · ".join(p for p in partes if p) or "em breve"


def pagina_indicadores(catalogo: dict) -> None:
    gerencias = catalogo.get("gerencia", [])
    cargas, motivo_sem_datas = ultimas_cargas()
    projetos = [p for g in gerencias for p in g.get("projeto", [])]
    no_ar = [p for p in projetos if categoria(p) == "No ar"]
    em_dev = [p for p in projetos if p.get("status") == "em construção"]
    pausados = sum(pausado(p) for p in em_dev)

    col_intro, col_ar, col_dev = st.columns([2, 1, 1])
    with col_intro:
        st.html(
            '<div class="hub-intro"><b>O Hub de Indicadores reúne, num só endereço, os painéis e dashboards de Gente & Dados '
            'da Pacaembu Construtora.</b><span class="hub-intro-mais"> Com informação confiável e atualizada sobre as pessoas '
            'da companhia, lideranças e RH decidem com base em dados: planejam o quadro, tratam remuneração e carreira com '
            'equidade e agem cedo sobre o que afeta a retenção. Cada card mostra de onde vêm os dados e quando foram '
            'atualizados; o botão leva direto ao painel.</span></div>')
    with col_ar:
        pp.kpi("Painéis no ar", str(len(no_ar)), "rodando para as gerências", pp.AZUL)
    with col_dev:
        pp.kpi("Em desenvolvimento", str(len(em_dev)),
               f"{pausados} {'pausado' if pausados == 1 else 'pausados'}" if pausados else "em construção", pp.CINZA_TXT)

    col_busca, col_status = st.columns([2, 3], vertical_alignment="bottom")
    termo = col_busca.text_input("Buscar", placeholder="Ex.: turnover, salário, Neon…", icon=":material/search:")
    filtro_status = col_status.pills("Status", FILTROS_STATUS, selection_mode="multi", default=FILTROS_STATUS) or FILTROS_STATUS

    algum = False
    for gerencia in gerencias:
        todos = gerencia.get("projeto", [])
        visiveis = [p for p in todos if categoria(p) in filtro_status and casa_busca(p, gerencia["nome"], termo)]
        vazia = not todos
        # Gerência sem nenhum projeto aparece como "em breve" (menos durante uma busca);
        # gerência com projetos mas nenhum passando no filtro some.
        if (vazia and termo) or (not vazia and not visiveis):
            continue
        algum = True
        # gerência "em breve" começa fechada; as que têm painel, abertas
        with st.expander(f"{gerencia.get('icone', '')} {gerencia['nome']}  ·  {resumo_gerencia(todos)}", expanded=not vazia):
            if vazia:
                st.caption(":material/hourglass_empty: Em breve — nenhum indicador publicado ainda.")
                continue
            for i in range(0, len(visiveis), 3):
                cols = st.columns(3)
                for col, projeto in zip(cols, visiveis[i:i + 3]):
                    with col:
                        card_projeto(projeto, cargas)

    if not algum:
        st.info("Nenhum indicador encontrado com esse filtro.", icon=":material/search_off:")
    if motivo_sem_datas:
        st.caption(f":material/info: Datas de atualização indisponíveis: {motivo_sem_datas}.")

    try:
        email = st.secrets["app"]["email_suporte"]
    except Exception:  # noqa: BLE001 — sem o bloco [app], o rodapé sai sem o e-mail
        email = None
    contato = f'Dúvidas ou pedido de acesso: <a href="mailto:{escape(email)}">{escape(email)}</a> · ' if email else ""
    st.html(f'<div class="hub-rodape">{contato}Central de Gente & Dados · Pacaembu Construtora</div>')


st.set_page_config(page_title="Hub de Indicadores · Pacaembu Construtora", page_icon=str(ROOT / "static" / "icone-hub.png"), layout="wide")

catalogo = carregar_catalogo(CATALOGO.stat().st_mtime)
st.html(pp._CSS_CORPO)  # cards pp.kpi, seções e notas no padrão dos painéis
st.html(CSS)

with st.container(horizontal=True, vertical_alignment="center", gap="medium"):
    # <img> direto (servido por static/) em vez de st.image, que arredonda os cantos
    # e deforma a bandeira gráfica do logo.
    st.html('<img src="app/static/pacaembu-horizontal-colorido.png" alt="Pacaembu Construtora" style="width:240px;border-radius:0;display:block">', width="content")
    with st.container(gap=None):
        st.title("Hub de Indicadores", anchor=False)
        st.caption("Central de Gente & Dados — Pacaembu Construtora")

pagina_indicadores(catalogo)
