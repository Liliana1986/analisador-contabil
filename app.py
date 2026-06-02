import streamlit as st
import pdfplumber
import anthropic
import json
import io

# ── Configuração da página ──────────────────────────────────────────────────
st.set_page_config(
    page_title="Analisador Contabilístico",
    page_icon="📊",
    layout="wide",
)

# ── CSS personalizado ───────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

.header-box {
    background: linear-gradient(135deg, #1e3a5f 0%, #2563eb 100%);
    color: white;
    padding: 24px 32px;
    border-radius: 14px;
    margin-bottom: 28px;
}
.header-box h1 { font-size: 1.6rem; font-weight: 700; margin: 0 0 4px 0; }
.header-box p  { font-size: 0.9rem; opacity: 0.85; margin: 0; }

.card {
    background: white;
    border-radius: 12px;
    padding: 22px 24px;
    border: 1.5px solid #e2e8f0;
    margin-bottom: 18px;
}
.card h3 {
    font-size: 0.82rem;
    text-transform: uppercase;
    letter-spacing: 0.7px;
    color: #2563eb;
    font-weight: 700;
    margin: 0 0 14px 0;
}

.indicator-row {
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
    margin-bottom: 4px;
}
.indicator {
    background: #f7fafd;
    border: 1.5px solid #e2e8f0;
    border-radius: 10px;
    padding: 12px 16px;
    min-width: 160px;
    flex: 1;
}
.indicator .lbl { font-size: 0.72rem; text-transform: uppercase; color: #718096; font-weight: 600; }
.indicator .val { font-size: 1.05rem; font-weight: 700; color: #1e3a5f; margin-top: 4px; }
.indicator.pos .val { color: #166534; }
.indicator.neg .val { color: #c53030; }

.resumo {
    background: #eff6ff;
    border-left: 4px solid #2563eb;
    border-radius: 0 10px 10px 0;
    padding: 16px 20px;
    font-size: 0.95rem;
    line-height: 1.7;
    color: #1a2332;
}

.conclusao {
    background: linear-gradient(135deg, #1e3a5f 0%, #2563eb 100%);
    color: white;
    border-radius: 12px;
    padding: 22px 26px;
    font-size: 0.95rem;
    line-height: 1.7;
}

.alert-item  { color: #c53030; padding: 6px 0; border-bottom: 1px solid #fff5f5; font-size: 0.92rem; }
.pos-item    { color: #166534; padding: 6px 0; border-bottom: 1px solid #f0fdf4; font-size: 0.92rem; }
.rec-item    { color: #1e3a5f; padding: 6px 0; border-bottom: 1px solid #eff6ff; font-size: 0.92rem; }

table { width: 100%; border-collapse: collapse; }
th { background: #f1f5f9; padding: 9px 12px; text-align: left; font-size: 0.76rem;
     text-transform: uppercase; color: #64748b; font-weight: 600; }
td { padding: 9px 12px; border-bottom: 1px solid #f1f5f9; font-size: 0.88rem; color: #1a2332; }
</style>
""", unsafe_allow_html=True)


# ── Extração de PDF ─────────────────────────────────────────────────────────
def extract_pdf(file_bytes: bytes) -> str:
    pages = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text()
            if text:
                pages.append(f"--- Página {i+1} ---\n{text}")
            tables = page.extract_tables()
            for table in tables:
                if table:
                    for row in table[:40]:
                        if row:
                            pages.append(" | ".join(str(c).strip() if c else "" for c in row))
    return "\n\n".join(pages)


# ── Análise com Claude ──────────────────────────────────────────────────────
SYSTEM = """És um contabilista certificado português com experiência em PME.
Analisas balancetes SNC e produzes relatórios claros para empresários sem conhecimentos técnicos.
Usa português de Portugal. Formata valores com € (ex: 12.345,67 €). Sê objetivo e prático."""

PROMPT = """Analisa o seguinte balancete e gera um relatório estruturado.

EMPRESA: {nome} | NIF: {nif} | Atividade: {atividade} | Período: {periodo}

BALANCETE:
{texto}

Responde APENAS com JSON válido nesta estrutura:
{{
  "resumo_executivo": "3-4 frases sobre a situação geral",
  "indicadores": {{
    "total_rendimentos": "valor € ou Não disponível",
    "total_gastos": "valor € ou Não disponível",
    "resultado_estimado": "valor €",
    "resultado_tipo": "Lucro / Prejuízo / Não determinado",
    "gastos_pessoal": "valor € ou Não disponível",
    "gastos_fse": "valor € ou Não disponível",
    "saldo_clientes": "valor € ou Não disponível",
    "saldo_fornecedores": "valor € ou Não disponível",
    "disponibilidades": "valor € ou Não disponível",
    "dividas_fiscais": "valor € ou Não identificado"
  }},
  "principais_rendimentos": [
    {{"conta": "código", "descricao": "nome", "valor": "valor €", "peso": "%"}}
  ],
  "principais_gastos": [
    {{"conta": "código", "descricao": "nome", "valor": "valor €", "peso": "%"}}
  ],
  "situacao_clientes_fornecedores": "2-3 frases",
  "tesouraria": "2-3 frases",
  "alertas": ["alerta 1", "alerta 2"],
  "pontos_positivos": ["ponto 1", "ponto 2"],
  "recomendacoes": ["recomendação prática 1", "recomendação 2"],
  "conclusao": "3-4 frases finais"
}}"""


def analisar(api_key: str, texto: str, nome: str, nif: str, atividade: str, periodo: str) -> dict:
    client = anthropic.Anthropic(api_key=api_key)
    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        system=SYSTEM,
        messages=[{"role": "user", "content": PROMPT.format(
            nome=nome, nif=nif, atividade=atividade, periodo=periodo,
            texto=texto[:15000]
        )}],
    )
    raw = msg.content[0].text.strip()
    if raw.startswith("```"):
        raw = "\n".join(raw.split("\n")[1:-1])
    return json.loads(raw)


# ── Interface ───────────────────────────────────────────────────────────────
st.markdown("""
<div class="header-box">
  <h1>📊 Analisador Contabilístico</h1>
  <p>Análise automática de balancetes para PME portuguesas</p>
</div>
""", unsafe_allow_html=True)

# Chave API na barra lateral
with st.sidebar:
    st.markdown("### ⚙️ Configuração")
    api_key = st.text_input(
        "Chave API Anthropic",
        type="password",
        placeholder="sk-ant-...",
        help="Obtenha em console.anthropic.com → API Keys"
    )
    st.markdown("---")
    st.markdown("**Como usar:**")
    st.markdown("1. Cole a chave API acima")
    st.markdown("2. Carregue o balancete PDF")
    st.markdown("3. Preencha os dados da empresa")
    st.markdown("4. Clique em **Gerar Análise**")
    st.markdown("---")
    st.caption("Análise gerada por IA · Valide sempre com o seu contabilista")

# Formulário principal
with st.form("form_analise"):
    st.markdown("### 📄 Balancete e Dados da Empresa")

    col1, col2 = st.columns([1, 1])
    with col1:
        pdf_file = st.file_uploader("Carregar balancete PDF", type=["pdf"])
        nome = st.text_input("Nome da empresa", placeholder="Ex: Exemplo, Lda.")
    with col2:
        nif = st.text_input("NIF", placeholder="Ex: 510 123 456")
        periodo = st.text_input("Período de análise", placeholder="Ex: 1.º Trimestre 2025")
        atividade = st.text_input("Atividade da empresa", placeholder="Ex: Comércio a retalho de vestuário")

    submitted = st.form_submit_button("🔍 Gerar Análise", use_container_width=True, type="primary")

# Processamento
if submitted:
    if not api_key:
        st.error("Por favor, insira a chave API Anthropic na barra lateral.")
    elif not pdf_file:
        st.error("Por favor, carregue o balancete em PDF.")
    elif not all([nome, nif, atividade, periodo]):
        st.error("Por favor, preencha todos os campos da empresa.")
    else:
        with st.spinner("A processar o balancete e a gerar a análise… (15–30 segundos)"):
            try:
                texto = extract_pdf(pdf_file.read())
                if not texto.strip():
                    st.error("Não foi possível extrair texto do PDF. O ficheiro pode estar em formato de imagem (scaneado). Use um PDF com texto seleccionável.")
                    st.stop()

                a = analisar(api_key, texto, nome, nif, atividade, periodo)
                ind = a.get("indicadores", {})

                # ── Resultado ──────────────────────────────────────────────
                st.success("✅ Análise concluída!")
                st.markdown(f"**{nome}** &nbsp;·&nbsp; NIF: {nif} &nbsp;·&nbsp; {atividade} &nbsp;·&nbsp; {periodo}")
                st.markdown("---")

                # Resumo executivo
                st.markdown('<div class="card"><h3>📋 Resumo Executivo</h3><div class="resumo">' +
                            a.get("resumo_executivo", "") + '</div></div>', unsafe_allow_html=True)

                # Indicadores
                st.markdown('<div class="card"><h3>📈 Indicadores Financeiros</h3>', unsafe_allow_html=True)
                c1, c2, c3 = st.columns(3)
                with c1:
                    st.metric("Total Rendimentos", ind.get("total_rendimentos", "—"))
                    st.metric("Gastos c/ Pessoal", ind.get("gastos_pessoal", "—"))
                    st.metric("Clientes", ind.get("saldo_clientes", "—"))
                with c2:
                    st.metric("Total Gastos", ind.get("total_gastos", "—"))
                    st.metric("Fornec. e Serv. Externos", ind.get("gastos_fse", "—"))
                    st.metric("Fornecedores", ind.get("saldo_fornecedores", "—"))
                with c3:
                    tipo = ind.get("resultado_tipo", "")
                    st.metric(f"Resultado ({tipo})", ind.get("resultado_estimado", "—"))
                    st.metric("Disponibilidades / Bancos", ind.get("disponibilidades", "—"))
                    if ind.get("dividas_fiscais", "Não identificado") != "Não identificado":
                        st.metric("⚠️ Dívidas Fiscais / SS", ind.get("dividas_fiscais"))
                st.markdown('</div>', unsafe_allow_html=True)

                # Rendimentos e gastos lado a lado
                col_r, col_g = st.columns(2)
                with col_r:
                    rend = a.get("principais_rendimentos", [])
                    if rend:
                        st.markdown("**📈 Principais Rendimentos**")
                        for r in rend:
                            st.markdown(f"**{r.get('conta','')}** — {r.get('descricao','')}  \n`{r.get('valor','')}` &nbsp; {r.get('peso','')}", unsafe_allow_html=True)
                            st.divider()

                with col_g:
                    gast = a.get("principais_gastos", [])
                    if gast:
                        st.markdown("**📉 Principais Gastos**")
                        for g in gast:
                            st.markdown(f"**{g.get('conta','')}** — {g.get('descricao','')}  \n`{g.get('valor','')}` &nbsp; {g.get('peso','')}", unsafe_allow_html=True)
                            st.divider()

                # Clientes/Fornecedores e Tesouraria
                col_cf, col_t = st.columns(2)
                with col_cf:
                    st.markdown("**👥 Clientes e Fornecedores**")
                    st.info(a.get("situacao_clientes_fornecedores", ""))
                with col_t:
                    st.markdown("**🏦 Tesouraria e Bancos**")
                    st.info(a.get("tesouraria", ""))

                # Alertas
                alertas = a.get("alertas", [])
                if alertas:
                    with st.expander("⚠️ Alertas e Riscos", expanded=True):
                        for al in alertas:
                            st.error(f"• {al}")

                # Pontos positivos
                pontos = a.get("pontos_positivos", [])
                if pontos:
                    with st.expander("✅ Pontos Positivos", expanded=True):
                        for p in pontos:
                            st.success(f"• {p}")

                # Recomendações
                recs = a.get("recomendacoes", [])
                if recs:
                    with st.expander("💡 Recomendações", expanded=True):
                        for r in recs:
                            st.info(f"• {r}")

                # Conclusão
                st.markdown("---")
                st.markdown('<div class="conclusao"><strong style="font-size:0.8rem;opacity:0.8;text-transform:uppercase;letter-spacing:0.7px;">Conclusão</strong><br><br>' +
                            a.get("conclusao", "") + '</div>', unsafe_allow_html=True)

                # Exportar JSON (para fase seguinte — PowerPoint)
                st.markdown("---")
                st.download_button(
                    label="⬇️ Descarregar análise (JSON)",
                    data=json.dumps(a, ensure_ascii=False, indent=2),
                    file_name=f"analise_{nome.replace(' ', '_')}_{periodo.replace(' ', '_')}.json",
                    mime="application/json",
                )

            except json.JSONDecodeError:
                st.error("Erro ao interpretar a resposta da IA. Tente novamente.")
            except anthropic.AuthenticationError:
                st.error("Chave API inválida. Verifique a chave Anthropic na barra lateral.")
            except Exception as e:
                st.error(f"Erro: {str(e)}")
