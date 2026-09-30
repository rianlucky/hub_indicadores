"""Padrão visual dos painéis Streamlit da Central de Gente & Dados (Pacaembu Construtora).

Modelo mantido na skill `padrao-painel-streamlit` (People Analytics/.claude/skills). Cada
painel tem a sua cópia deste arquivo (o deploy no Streamlit Cloud é por repositório).

Barra lateral, sempre nesta ordem:
    1. Logo: ícone do painel + nome (st.logo, fixo no topo)
    2. "Olá, {nome}" + botão Sair   (quando há login; em desenvolvimento, aviso discreto)
    3. Abas / páginas, se houver   (st.navigation ou st.radio, feito pelo painel)
    4. Filtros                      (feitos pelo painel dentro do `with barra_lateral(...)`)
    5. Fonte e Atualizado em        (mesmo visual do card do Hub de Indicadores)

Uso:
    import painel_padrao as pp
    pp.logo("assets/icone.png", "Turnover")
    with pp.barra_lateral(fonte="Neon + Databricks", atualizado_em=datetime(...)):
        st.multiselect(...)
"""
from __future__ import annotations

import contextlib
import hashlib
import json
from datetime import date, datetime
from html import escape
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

AZUL = "#064D66"
AZUL_ESCURO = "#003244"
AMARELO = "#FAB900"
FUSO = ZoneInfo("America/Sao_Paulo")

_CSS = f"""<style>
[data-testid="stSidebar"] .pp-ola {{ color:{AZUL_ESCURO}; font-size:.95rem; margin:.1rem 0 .35rem; }}
[data-testid="stSidebar"] .pp-dev {{ color:#7A8C96; font-size:.78rem; margin:.1rem 0 .35rem; }}
[data-testid="stSidebar"] .pp-meta {{ background:#F3F6F8; border-radius:10px; padding:.55rem .75rem;
    font-size:.8rem; border-left:4px solid {AMARELO}; margin-top:.4rem; }}
[data-testid="stSidebar"] .pp-meta div {{ display:flex; gap:.5rem; padding:.12rem 0; color:{AZUL_ESCURO}; }}
[data-testid="stSidebar"] .pp-meta span {{ flex:0 0 5.9rem; color:#7A8C96; font-weight:600; font-size:.74rem; white-space:nowrap; }}
</style>"""


@st.cache_resource
def _wordmark(icone: str, titulo: str):
    """Ícone + nome do painel numa imagem só (st.logo aceita só imagem). Mesmo padrão do
    Headcount Total e da Aderência Salarial."""
    try:
        from PIL import Image, ImageDraw, ImageFont
        img = Image.open(icone).convert("RGBA")
        alt = 64
        img = img.resize((int(img.width * alt / img.height), alt))
        fonte = None
        for f in (r"C:\Windows\Fonts\segoeuib.ttf", r"C:\Windows\Fonts\arialbd.ttf",
                  "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
            if Path(f).exists():
                fonte = ImageFont.truetype(f, 34)
                break
        fonte = fonte or ImageFont.load_default(size=34)  # Pillow >= 10.1: fonte escalável, não a de 11px
        caixa = ImageDraw.Draw(Image.new("RGBA", (1, 1))).textbbox((0, 0), titulo, font=fonte)
        larg, alt_txt = caixa[2] - caixa[0], caixa[3] - caixa[1]
        tela = Image.new("RGBA", (img.width + 14 + larg + 4, alt), (0, 0, 0, 0))
        tela.paste(img, (0, 0), img)
        ImageDraw.Draw(tela).text((img.width + 14, (alt - alt_txt) // 2 - caixa[1]), titulo, font=fonte, fill=AZUL)
        return tela
    except Exception:  # noqa: BLE001 — sem PIL/fonte, cai só no ícone
        return None


# ----------------------------------------------------------------------------- corpo da página
# Cabeçalho (título + selos de atualização e de filtros), cards de KPI com o recorte em seta da
# bandeira da marca, títulos de seção e de gráfico. Padrão de 29/09/2026 (polimento do Headcount).
VERMELHO, VERDE, CINZA_TXT, CINZA_ESC_TXT, BORDA_CARD = "#F02727", "#22C55E", "#6B7280", "#1F2937", "#CBD8DE"

_CSS_CORPO = f"""<style>
h1 {{ font-weight: 800 !important; color: {AZUL_ESCURO} !important; letter-spacing: -.01em; }}
.pp-chips {{ display:flex; flex-wrap:wrap; gap:.4rem; margin:-.35rem 0 .9rem; }}
.pp-chip {{ display:inline-flex; align-items:center; gap:.3rem; max-width:100%; background:#EAF4F7; color:{AZUL};
    border:1px solid #CFE3EA; border-radius:999px; padding:.2rem .7rem; font-size:.78rem; font-weight:700; line-height:1.3; }}
.pp-chip span {{ color:{CINZA_TXT}; font-weight:600; }}
.pp-chip em {{ font-style:normal; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
.pp-chip.pp-atualizado {{ background:#FFF6DB; border-color:#FBE3A0; color:#7A5400; }}
.pp-chip.pp-sem-filtro {{ background:#F3F4F6; border-color:#E5E7EB; color:{CINZA_TXT}; }}
.pp-kpi {{ position:relative; background:#FFFFFF; border:1px solid {BORDA_CARD}; border-radius:12px; height:100%;
    display:flex; flex-direction:column; box-shadow:0 1px 2px rgba(6,77,102,.05); }}
.pp-kpi-topo {{ background:{AZUL}; color:#FFFFFF; font-weight:800; font-size:.72rem; letter-spacing:.05em;
    text-transform:uppercase; line-height:1.25; padding:.45rem 1.7rem .45rem .85rem; width:calc(100% - 10px);
    box-sizing:border-box; border-top-left-radius:11px; clip-path:polygon(0 0, calc(100% - 15px) 0, 100% 50%, calc(100% - 15px) 100%, 0 100%); }}
.pp-kpi-valor {{ color:{CINZA_ESC_TXT}; font-size:1.85rem; font-weight:800; text-align:center; padding:.6rem .5rem .05rem;
    flex:1; display:flex; align-items:center; justify-content:center; line-height:1.1; }}
.pp-kpi-nota {{ text-align:center; font-size:.78rem; font-weight:700; min-height:1.15rem; padding:0 .6rem .55rem; }}
.pp-kpi-base {{ height:7px; background:{AMARELO}; border-radius:0 0 11px 11px; }}
/* "i" de ajuda: desenhado em CSS (nítido em qualquer tela; o st.html remove SVG), no canto de cima do valor,
   ao lado da nota, com dica própria ao passar o mouse ou tocar */
.pp-kpi-ajuda {{ position:relative; display:inline-block; vertical-align:-3px; margin-left:5px; width:16px; height:16px; box-sizing:border-box;
    border:1.6px solid #9FB3BD; border-radius:50%; cursor:help; outline:none; z-index:5; transition:border-color .15s; }}
.pp-kpi-ajuda::before, .pp-kpi-ajuda::after {{ content:""; position:absolute; left:50%; background:#9FB3BD;
    transform:translateX(-50%); transition:background .15s; }}
.pp-kpi-ajuda::before {{ top:2.6px; width:2.2px; height:2.2px; border-radius:50%; }}
.pp-kpi-ajuda::after {{ top:5.8px; width:1.7px; height:5.4px; border-radius:1px; }}
.pp-kpi-ajuda:hover, .pp-kpi-ajuda:focus {{ border-color:{AZUL}; }}
.pp-kpi-ajuda:hover::before, .pp-kpi-ajuda:hover::after, .pp-kpi-ajuda:focus::before, .pp-kpi-ajuda:focus::after {{ background:{AZUL}; }}
.pp-kpi-dica {{ position:absolute; top:calc(100% + 9px); left:50%; width:270px; max-width:80vw; background:#003244;
    color:#FFFFFF; font-size:.78rem; font-weight:500; line-height:1.45; letter-spacing:0; text-transform:none; text-align:left; white-space:normal;
    overflow-wrap:break-word;
    padding:.6rem .75rem; border-radius:8px; box-shadow:0 6px 18px rgba(0,50,68,.25); opacity:0; visibility:hidden;
    transform:translate(-50%, -3px); transition:opacity .15s, transform .15s; pointer-events:none; z-index:1000; }}
.pp-kpi-dica::before {{ content:""; position:absolute; top:-5px; left:calc(50% - 5px); width:10px; height:10px; background:#003244;
    transform:rotate(45deg); }}
.pp-kpi-ajuda:hover .pp-kpi-dica, .pp-kpi-ajuda:focus .pp-kpi-dica {{ opacity:1; visibility:visible; transform:translate(-50%, 0); }}
/* no último card da linha a dica abre para a esquerda, sem sair da tela */
[data-testid="stColumn"]:last-child .pp-kpi-dica {{ left:auto; right:-8px; transform:translate(0, -3px); }}
[data-testid="stColumn"]:last-child .pp-kpi-dica::before {{ left:auto; right:11px; }}
[data-testid="stColumn"]:last-child .pp-kpi-ajuda:hover .pp-kpi-dica,
[data-testid="stColumn"]:last-child .pp-kpi-ajuda:focus .pp-kpi-dica {{ transform:none; }}
[data-testid="stElementContainer"]:has(.pp-kpi-ajuda:hover), [data-testid="stElementContainer"]:has(.pp-kpi-ajuda:focus),
[data-testid="stColumn"]:has(.pp-kpi-ajuda:hover), [data-testid="stColumn"]:has(.pp-kpi-ajuda:focus) {{ position:relative; z-index:1000; }}
.secao {{ color:{AZUL}; font-weight:800; font-size:1.08rem; border-bottom:3px solid {AMARELO};
    display:inline-block; padding-bottom:.15rem; margin:.7rem 0 .2rem; }}
.titulo-graf {{ color:{CINZA_ESC_TXT}; font-weight:700; font-size:.95rem; margin-bottom:-.4rem; }}
.nota {{ color:{CINZA_TXT}; font-size:.8rem; line-height:1.4; }}
/* cards da mesma fileira sempre com a mesma altura (a do mais alto), em qualquer largura de tela */
[data-testid="stVerticalBlock"] > [data-testid="stElementContainer"]:has(> [data-testid="stHtml"] > .pp-kpi) {{
    flex:1 1 auto; display:flex; flex-direction:column; }}
[data-testid="stHtml"]:has(> .pp-kpi) {{ flex:1 1 auto; display:flex; flex-direction:column; }}
[data-testid="stHtml"] > .pp-kpi {{ flex:1 1 auto; }}
@media (max-width: 640px) {{ .pp-kpi-valor {{ font-size:1.55rem; }} }}
/* Impressão (Ctrl+P / PDF): A4 deitada, só o conteúdo — os filtros já estão nos selos do topo */
@media print {{
  @page {{ size: A4 landscape; margin: 9mm 10mm; }}
  html, body {{ -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; background: #FFFFFF !important; }}
  [data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"], [data-testid="stHeader"], [data-testid="stToolbar"],
  [data-testid="stDecoration"], [data-testid="stStatusWidget"], [data-testid="stElementToolbar"], [data-testid="stDownloadButton"],
  [data-testid="stButtonGroup"], [data-testid="stSegmentedControl"], [data-testid="stSelectbox"], [data-testid="stMultiSelect"],
  [data-testid="stButton"], iframe[title="streamlit_analytics"] {{ display: none !important; }}
  .stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"], section.main {{
      position: static !important; overflow: visible !important; height: auto !important; min-height: 0 !important; }}
  [data-testid="stMainBlockContainer"] {{ max-width: 100% !important; padding: 0 !important; margin: 0 !important; }}
  canvas, svg.marks, [data-testid="stVegaLiteChart"] > div, .vega-embed {{ max-width: 100% !important; }}
  canvas {{ height: auto !important; }}
  .pp-kpi, .pp-chips, [data-testid="stVegaLiteChart"], .stVegaLiteChart, [data-testid="stDeckGlJsonChart"],
  [data-testid="stDataFrame"], [data-testid="stHorizontalBlock"] {{ break-inside: avoid; page-break-inside: avoid; }}
  .secao, .titulo-graf {{ break-after: avoid; page-break-after: avoid; }}
  /* cada seção (menos a primeira) começa numa folha nova: o título nunca fica sozinho no pé da página */
  [data-testid="stElementContainer"]:has(.pp-nova-folha) {{ break-before: page; page-break-before: always; }}
  h1 {{ font-size: 1.9rem !important; margin-top: 0 !important; }}
  .pp-kpi-ajuda {{ display: none !important; }}
}}
</style>"""


def _valores_chip(valores, maximo: int = 2) -> tuple[str, str]:
    """Texto curto do selo ("A, B +3") e o texto completo (tooltip)."""
    if isinstance(valores, str):
        return valores, valores
    lista = [str(v) for v in valores]
    completo = ", ".join(lista)
    curto = ", ".join(lista[:maximo]) + (f" +{len(lista) - maximo}" if len(lista) > maximo else "")
    return curto, completo


def cabecalho(titulo: str, atualizado_em=None, filtros: dict | None = None, legenda: str | None = None) -> None:
    """Título do painel (Nunito, como o Hub) + selos: um de "Atualizado em" e um por filtro em uso.
    Os selos ficam no topo de propósito: num print ou PDF da página, os filtros aplicados vão junto.
    `filtros` = {"Diretoria": [...], "Período": "01/09/2025 a 28/09/2026"}; listas vazias são
    ignoradas. Com mais de 2 valores o selo mostra "A, B +N" (lista completa no tooltip)."""
    st.html(_CSS_CORPO)
    st.session_state["_pp_secao_na_pagina"] = False  # recomeça a contagem de seções a cada execução
    st.title(titulo, anchor=False)
    selos = []
    if atualizado_em is not None:
        selos.append(f'<span class="pp-chip pp-atualizado"><span>Atualizado em</span><em>{escape(_formatar(atualizado_em))}</em></span>')
    ativos = {k: v for k, v in (filtros or {}).items() if v}
    for nome, valores in ativos.items():
        curto, completo = _valores_chip(valores)
        selos.append(f'<span class="pp-chip" title="{escape(nome)}: {escape(completo)}"><span>{escape(nome)}</span><em>{escape(curto)}</em></span>')
    if not any(k != "Período" for k in ativos):
        selos.append('<span class="pp-chip pp-sem-filtro">Sem filtros · toda a empresa</span>')
    st.html(f'<div class="pp-chips">{"".join(selos)}</div>')
    if legenda:
        st.caption(legenda)


def _nota_com_icone(nota: str, icone: str) -> str:
    """Última palavra da nota e o "i" presos na mesma linha (o ícone nunca cai sozinho)."""
    if not icone:
        return escape(nota)
    inicio, _, ultima = nota.rpartition(" ")
    return f'{escape(inicio)}{" " if inicio else ""}<span style="white-space:nowrap">{escape(ultima)}{icone}</span>'


def kpi(rotulo: str, valor: str, nota: str = "", cor_nota: str = CINZA_TXT, ajuda: str | None = None) -> None:
    """Card de KPI: faixa azul com o recorte em seta da bandeira da marca (clip-path, acompanha
    qualquer largura de tela), valor grande, nota colorida e faixa amarela embaixo. `ajuda` põe um
    "i" ao lado da nota do card com a explicação ao passar o mouse ou tocar (conceitos como compa-ratio).
    Use só no card do conceito — não repita a mesma explicação em todos os cards."""
    tam = "" if len(valor) <= 7 else ' style="font-size:1.45rem"' if len(valor) <= 10 else ' style="font-size:1.2rem"'
    icone = (f'<span class="pp-kpi-ajuda" tabindex="0" role="note" aria-label="{escape(ajuda)}">'
             f'<span class="pp-kpi-dica">{escape(ajuda)}</span></span>' if ajuda else "")
    st.html(f'<div class="pp-kpi"><div class="pp-kpi-topo">{escape(rotulo)}</div>'
            f'<div class="pp-kpi-valor"{tam}>{escape(valor)}</div>'
            f'<div class="pp-kpi-nota" style="color:{cor_nota}">{_nota_com_icone(nota, icone)}</div><div class="pp-kpi-base"></div></div>')


def secao(titulo: str, nova_folha: bool | None = None) -> None:
    """Título de seção. Na impressão, toda seção depois da primeira começa numa folha nova.
    `nova_folha=True` força também na primeira (quando o conteúdo dela não cabe abaixo dos cards:
    a primeira folha vira uma capa com título, selos e cards)."""
    primeira = not st.session_state.get("_pp_secao_na_pagina")
    st.session_state["_pp_secao_na_pagina"] = True
    quebra = (not primeira) if nova_folha is None else nova_folha
    st.html(f'<div class="secao{" pp-nova-folha" if quebra else ""}">{escape(titulo)}</div>')


def logo(icone: str | Path, titulo: str) -> None:
    """Usa assets/logo-wordmark.png (ícone + nome já desenhados) quando existe. Gerar a imagem na
    hora depende das fontes do Windows, que o Streamlit Cloud (Linux) não tem: lá o nome saía
    minúsculo (fonte de emergência de ~11px). Ver a skill padrao-painel-streamlit."""
    icone = Path(icone)
    pronto = icone.parent / "logo-wordmark.png"
    marca = str(pronto) if pronto.exists() else _wordmark(str(icone), titulo)
    st.logo(marca if marca is not None else str(icone), icon_image=str(icone), size="large")


def _conta() -> None:
    usuario = st.session_state.get("auth_user")
    if usuario:
        st.html(f'<div class="pp-ola">Olá, <b>{escape(usuario.get("name") or usuario.get("email", ""))}</b></div>')
        if st.button("Sair", key="pp_sair", width="stretch", icon=":material/logout:"):
            st.session_state["auth_user"] = None
            st.session_state["auth_email"] = None
            st.rerun()
    else:
        st.html('<div class="pp-dev">Modo desenvolvimento · sem login</div>')
    st.divider()


def _formatar(valor) -> str:
    if isinstance(valor, datetime):
        if valor.tzinfo is not None:
            valor = valor.astimezone(FUSO)
        return f"{valor:%d/%m/%Y %H:%M}"
    if isinstance(valor, date):
        return f"{valor:%d/%m/%Y}"
    return str(valor)


def rodape(fonte: str, atualizado_em=None, extra: dict[str, str] | None = None) -> None:
    linhas = {"Fonte": fonte}
    if atualizado_em is not None:
        linhas["Atualizado em"] = _formatar(atualizado_em)
    linhas |= extra or {}
    corpo = "".join(f"<div><span>{escape(k)}</span>{escape(str(v))}</div>" for k, v in linhas.items())
    st.html(f'<div class="pp-meta">{corpo}</div>')


@contextlib.contextmanager
def barra_lateral(fonte: str, atualizado_em=None, extra: dict[str, str] | None = None):
    """Monta a barra lateral no padrão: conta no topo, o conteúdo do `with` (abas e filtros)
    no meio, Fonte/Atualizado em no fim."""
    with st.sidebar:
        st.html(_CSS)
        _conta()
        yield
        st.divider()
        rodape(fonte, atualizado_em, extra)


# ----------------------------------------------------------------------------- gráficos (Vega-Lite)
# Use pp.grafico(titulo, spec, altura) em todo gráfico. Ele: mostra o aviso "i" quando não há dados
# no filtro; leva os dados para dentro das camadas em JSON seguro; e passa uma key que muda com os
# dados — sem isso, gráficos com camadas não redesenhavam quando o filtro mudava (Turnover, 28/09).
FONTE_GRAFICO, CINZA, CINZA_ESCURO, BORDA, GRID = "Nunito", "#6B7280", "#1F2937", "#CBD8DE", "#E5EDF1"


def _config() -> dict:
    return {"view": {"stroke": None}, "font": FONTE_GRAFICO,
            "axis": {"labelFont": FONTE_GRAFICO, "labelFontSize": 11, "labelColor": CINZA, "domainColor": BORDA,
                     "gridColor": GRID, "tickColor": BORDA, "title": None},
            "legend": {"labelFont": FONTE_GRAFICO, "labelFontSize": 11, "labelColor": CINZA_ESCURO, "title": None, "orient": "top"}}


SEM_DADOS = "Sem desligamentos no filtro selecionado."


def _linhas(spec) -> list[dict]:
    """Todas as linhas de dados do spec (no topo e dentro das camadas)."""
    out = []
    if isinstance(spec, dict):
        out += (spec.get("data") or {}).get("values") or []
        for camada in spec.get("layer", []):
            out += _linhas(camada)
    return out


def _sem_dados(spec: dict) -> bool:
    """Nada para desenhar: sem linhas, ou todas as contagens zeradas (donut/funil de uma área sem
    desligados quebraria o gráfico)."""
    linhas = _linhas(spec)
    if not linhas:
        return True
    campos = [c for c in ("desligamentos", "admitidos", "desligamentos_voluntario", "desligamentos_involuntario")
              if c in linhas[0]]
    return bool(campos) and all(not (r.get(c) or 0) for r in linhas for c in campos)


def _json_seguro(linhas: list[dict]) -> list[dict]:
    return json.loads(pd.DataFrame(linhas).to_json(orient="records", date_format="iso")) if linhas else []


def _dados_nas_camadas(spec: dict) -> dict:
    """Leva os dados do topo para cada camada do primeiro nível (em JSON seguro). Com os dados no
    topo e várias camadas, o Streamlit separa os dados do desenho e o navegador às vezes não
    redesenha quando o filtro muda (evolução e donut de motivos, 28/09).
    Um grupo de camadas recebe os dados no próprio nível do grupo — junto com o transform dele
    (ex.: fold das séries); dar dados às camadas internas faria elas ignorarem esse transform."""
    spec = dict(spec)
    topo = spec.pop("data", None)
    if "layer" not in spec:
        if topo is not None:
            spec["data"] = {"values": _json_seguro(topo.get("values", []))}
        return spec
    camadas = []
    for camada in spec["layer"]:
        camada = dict(camada)
        dados = camada.get("data") or topo
        if dados is not None:
            camada["data"] = {"values": _json_seguro(dados.get("values", []))}
        camadas.append(camada)
    spec["layer"] = camadas
    return spec


def grafico(titulo: str, spec: dict, altura: int = 300, aviso: str = SEM_DADOS) -> None:
    st.html(f'<div class="titulo-graf">{titulo}</div>')
    if _sem_dados(spec):
        st.info(aviso, icon=":material/info:")
        return
    spec = _dados_nas_camadas(spec)
    spec = {"$schema": "https://vega.github.io/schema/vega-lite/v5.json", "height": altura, "config": _config(), **spec}
    # key muda junto com os dados: o Streamlit manda os dados separados do desenho e, em gráficos
    # com várias camadas, só trocar os dados às vezes não redesenha — com a key nova, redesenha sempre
    chave = hashlib.md5(json.dumps(spec, sort_keys=True, default=str).encode()).hexdigest()
    st.vega_lite_chart(spec, width="stretch", key=f"graf-{chave}")


