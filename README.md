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
