"""Hub de Indicadores — Central de Gente & Dados (Pacaembu Construtora).

Página única com todos os indicadores, agrupados por gerência e projeto. O conteúdo
vem de `indicadores.toml` — para incluir um indicador, edite só esse arquivo.
Sem login: é só uma página de links, e cada painel tem a própria senha.

    streamlit run app.py
"""

from __future__ import annotations

import re
import tomllib
import unicodedata
from datetime import datetime, timedelta
from html import escape
from pathlib import Path
from zoneinfo import ZoneInfo

import psycopg2

import streamlit as st

ROOT = Path(__file__).resolve().parent
CATALOGO = ROOT / "indicadores.toml"
FUSO = ZoneInfo("America/Sao_Paulo")

STATUS = {
    "no ar": ("No ar", "noar"),
    "em construção": ("Em construção", "construcao"),
}
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
  border-radius: 16px !important;
  border: 1px solid #E3E9ED !important;
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
[class*="st-key-card-ideia"] { border-top: 4px solid #B8C4CC !important; }

.st-key-hub-intro {
  background: #F3F6F8; border: none !important; border-left: 4px solid #FAB900 !important;
  border-radius: 12px !important; justify-content: center;
}
.st-key-hub-intro p { color: #003244; font-size: .92rem; line-height: 1.5; margin: 0; }

.hub-head { display: flex; align-items: center; gap: .85rem; }
.hub-logo {
  flex: 0 0 56px; height: 56px; border-radius: 14px; background: #F3F6F8;
  display: flex; align-items: center; justify-content: center;
}
.hub-logo img { max-width: 40px; max-height: 40px; border-radius: 0; }
.hub-iniciais { color: #064D66; font-weight: 800; font-size: 1.05rem; letter-spacing: .02em; }
.hub-nome { font-weight: 800; font-size: 1.08rem; color: #003244; line-height: 1.2; }
.hub-status {
  display: inline-flex; align-items: center; gap: .35rem; margin-top: .3rem;
  font-size: .74rem; font-weight: 700; padding: .12rem .55rem; border-radius: 999px;
}
.hub-status::before { content: ""; width: .45rem; height: .45rem; border-radius: 50%; background: currentColor; }
.hub-status.noar { color: #0B6B45; background: #E5F4EC; }
.hub-status.construcao { color: #8A5B00; background: #FFF3D1; }
.hub-status.ideia { color: #5B6B75; background: #EEF2F4; }
.hub-selos { display: flex; flex-wrap: wrap; gap: .3rem; align-items: center; }
/* "Pausado": selo cinza com a explicação num balão ao passar o mouse (ou tocar) */
.hub-status.pausado { position: relative; color: #5B6B75; background: #EEF2F4; cursor: help; outline: none; }
.hub-status.pausado::after {
  content: attr(data-dica); position: absolute; top: calc(100% + 8px); right: 0; z-index: 20;
  width: max-content; max-width: 260px; white-space: normal; background: #003244; color: #FFFFFF;
  font-size: .76rem; font-weight: 500; line-height: 1.45; padding: .55rem .7rem; border-radius: 8px;
  box-shadow: 0 6px 18px rgba(0, 50, 68, .25); opacity: 0; visibility: hidden; transition: opacity .15s;
}
.hub-status.pausado:hover::after, .hub-status.pausado:focus::after { opacity: 1; visibility: visible; }
[class*="st-key-card-"]:has(.hub-status.pausado:hover), [class*="st-key-card-"]:has(.hub-status.pausado:focus) { overflow: visible; z-index: 5; }
.hub-desc { color: #4A5E69; font-size: .9rem; line-height: 1.45; margin: .85rem 0 .75rem; }
.hub-meta { background: #F7F9FA; border-radius: 10px; padding: .55rem .75rem; font-size: .8rem; }
.hub-meta div { display: flex; gap: .5rem; padding: .12rem 0; color: #003244; }
.hub-meta span { flex: 0 0 6.6rem; color: #7A8C96; font-weight: 600; }
.hub-erro { color: #C41E1E; font-weight: 700; }
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
    # [neon_hub] = app_hub, só leitura em ops.v_ultima_carga (migração 008).
    try:
        url = st.secrets["neon_hub"]["database_url"]
    except Exception:  # noqa: BLE001 — secrets.toml ausente ou sem o bloco
        return {}, "o bloco [neon_hub] com database_url não foi encontrado nos Secrets"
    try:
        return _ler_cargas(url), None
    except psycopg2.OperationalError as exc:
        if "password authentication failed" in str(exc):
            return {}, "o Neon recusou a senha do app_hub"
        return {}, "não foi possível conectar ao Neon"
    except Exception as exc:  # noqa: BLE001 — o Hub continua de pé sem o Neon
        return {}, f"erro ao ler as cargas ({type(exc).__name__})"


def texto_atualizacao(projeto: dict, cargas: dict) -> str:
    registro = cargas.get(projeto.get("carga", ""))
    if not registro or registro[0] is None:
        diaria = projeto.get("atualizacao_diaria")
        if diaria:
            # Atualização fixa todo dia nesse horário: hoje, se já passou; senão, ontem.
            hora, minuto = (int(x) for x in diaria.split(":"))
            agora = datetime.now(FUSO)
            ultima = agora.replace(hour=hora, minute=minuto, second=0, microsecond=0)
            if agora < ultima:
                ultima -= timedelta(days=1)
            return ultima.strftime("%d/%m/%Y às %H:%M")
        return escape(projeto.get("atualizacao", ""))
    quando, status = registro
    texto = quando.astimezone(FUSO).strftime("%d/%m/%Y às %H:%M")
    if status != "ok":
        texto += ' · <span class="hub-erro">erro na última carga</span>'
    return texto


def casa_busca(projeto: dict, gerencia: str, termo: str) -> bool:
    if not termo:
        return True
    texto = " ".join(
        str(projeto.get(k, "")) for k in ("nome", "descricao", "fonte")
    ) + " " + gerencia
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
    rotulo = projeto.get("rotulo_status", rotulo)  # ex.: "Em desenvolvimento" no lugar de "Em construção"
    selos = f'<span class="hub-status {classe}">{escape(rotulo)}</span>'
    if projeto.get("pausado"):
        selos += (f'<span class="hub-status pausado" tabindex="0" data-dica="{escape(projeto["pausado"])}" '
                  f'aria-label="{escape(projeto["pausado"])}">Pausado</span>')
    logo = projeto.get("logo")
    if logo and (ROOT / "static" / "logos" / logo).exists():
        tile = f'<div class="hub-logo"><img src="app/static/logos/{escape(logo)}" alt=""></div>'
    else:
        tile = f'<div class="hub-logo"><span class="hub-iniciais">{escape(_iniciais(projeto["nome"]))}</span></div>'
    meta = "".join(
        f"<div><span>{rotulo_meta}</span>{valor}</div>"
        for rotulo_meta, valor in (
            ("Fonte", escape(projeto.get("fonte", ""))),
            ("Atualizado em", texto_atualizacao(projeto, cargas)),
        )
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


def pagina_indicadores(catalogo: dict) -> None:
    gerencias = catalogo.get("gerencia", [])
    cargas, motivo_sem_datas = ultimas_cargas()
    projetos = [p for g in gerencias for p in g.get("projeto", [])]

    col_intro, col_ar, col_construcao = st.columns([2, 1, 1])
    with col_intro, st.container(border=True, height="stretch", key="hub-intro"):
        st.markdown(
            "**O Hub de Indicadores reúne, num só endereço, os painéis e dashboards de Gente & Dados "
            "da Pacaembu Construtora.** Com informação confiável e atualizada sobre as pessoas da companhia, "
            "lideranças e RH decidem com base em dados: planejam o quadro, tratam remuneração e carreira com "
            "equidade e agem cedo sobre o que afeta a retenção. Cada card mostra de onde vêm os dados e quando "
            "foram atualizados; o botão leva direto ao painel."
        )
    col_ar.metric("Indicadores no ar", sum(p.get("status") == "no ar" for p in projetos), border=True, height="stretch")
    col_construcao.metric("Em construção", sum(p.get("status") == "em construção" for p in projetos), border=True, height="stretch")

    col_busca, col_status = st.columns([2, 3], vertical_alignment="bottom")
    termo = col_busca.text_input("Buscar", placeholder="Ex.: turnover, salário, Neon…", icon=":material/search:")
    filtro_status = col_status.pills(
        "Status", [v[0] for v in STATUS.values()], selection_mode="multi", default=["No ar", "Em construção"]
    )
    status_ok = {k for k, v in STATUS.items() if v[0] in (filtro_status or [])}

    algum = False
    for gerencia in gerencias:
        visiveis = [
            p for p in gerencia.get("projeto", [])
            if p.get("status") in (status_ok or STATUS) and casa_busca(p, gerencia["nome"], termo)
        ]
        vazia = not gerencia.get("projeto")
        # Gerência sem nenhum projeto aparece como "em breve" (menos durante uma busca);
        # gerência com projetos mas nenhum passando no filtro some.
        if (vazia and termo) or (not vazia and not visiveis):
            continue
        algum = True
        st.subheader(f"{gerencia.get('icone', '')} {gerencia['nome']}", divider="gray")
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


st.set_page_config(page_title="Hub de Indicadores · Gente & Dados", page_icon=":material/hub:", layout="wide")

catalogo = carregar_catalogo(CATALOGO.stat().st_mtime)
st.html(CSS)

with st.container(horizontal=True, vertical_alignment="center", gap="medium"):
    # <img> direto (servido por static/) em vez de st.image, que arredonda os cantos
    # e deforma a bandeira gráfica do logo.
    st.html('<img src="app/static/pacaembu-horizontal-colorido.png" alt="Pacaembu Construtora" style="width:240px;border-radius:0;display:block">', width="content")
    with st.container(gap=None):
        st.title("Hub de Indicadores", anchor=False)
        st.caption("Central de Gente & Dados — Pacaembu Construtora")

pagina_indicadores(catalogo)
