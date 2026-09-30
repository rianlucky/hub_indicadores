# Hub de Indicadores — Central de Gente & Dados

Página única em Streamlit com todos os indicadores do time, agrupados por
**gerência → projeto**. Cada card leva ao painel, dashboard ou relatório
correspondente. **Sem login**: é só uma página de links, e cada painel tem a
própria senha. Para publicar no Streamlit Cloud, cole o bloco `[neon_hub]` (ver `.streamlit/secrets.toml.example`) nos Secrets do app.

## Rodar

```powershell
streamlit run app.py
```

## Arquivos

| Arquivo | Para quê |
|---|---|
| `indicadores.toml` | **O catálogo.** Gerências, projetos e links (a lista de ideias fica guardada no fim do arquivo, sem aparecer na página). É o único arquivo que precisa mudar para o Hub crescer. |
| `app.py` | O app Streamlit que lê o catálogo e monta a página. |
| `.streamlit/config.toml` | Tema com a paleta oficial Pacaembu Construtora. |
| `static/` | Logo oficial. |

## Adicionar um indicador

1. Em `indicadores.toml`, copie um bloco `[[gerencia.projeto]]` para dentro da gerência certa.
2. Preencha `nome`, `descricao`, `status` (`no ar`, `em construção` ou `ideia`), `fonte`,
   `atualizacao`, `acesso` e um ou mais `[[gerencia.projeto.link]]` com `rotulo`, `tipo` e `url`.
3. Salve e recarregue a página — o Hub relê o catálogo sozinho.

Link com `url = ""` aparece no Hub como "link pendente".

## Padrão visual da Central (30/09/2026)

- Fundo claro e cards brancos como nos painéis; resumo em cards `pp.kpi` (painéis no ar e em desenvolvimento) ao lado do texto de apresentação.
- Gerências em blocos que abrem e fecham, com a contagem no título ("2 no ar · 1 em desenvolvimento"); as "em breve" começam fechadas.
- "Em construção" aparece como **Em desenvolvimento**; filtro de status com **Pausado**.
- Ponto de atualização no card: verde = carga de hoje, amarelo = mais antiga, vermelho = a última carga falhou.
- Selo **Novidade** por 3 semanas, com "O que mudou" no balão: campos `novidade` e `novidade_data` do `indicadores.toml`.
- Ícones de Movimentações e Estudos Salariais e ícone da aba (bandeira gráfica), nas cores da marca.
- Rodapé com o e-mail de suporte dos Secrets (`[app] email_suporte`).

**Para voltar à versão anterior:** `git checkout hub-v1-antes-padrao-visual -- app.py indicadores.toml .streamlit/config.toml` (tag no GitHub).
