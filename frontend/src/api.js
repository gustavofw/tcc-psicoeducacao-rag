// ============================================================
// api.js - Funções que conversam com a API (back-end FastAPI)
// ============================================================
// Centraliza todas as chamadas à API num lugar só. Assim, se a
// URL do back-end mudar, você altera apenas aqui.
// ============================================================

// Endereço da sua API. Em desenvolvimento é localhost:8000.
// Quando publicar no Railway, troca por esta URL.
const API_URL = "http://localhost:8000";

// ------------------------------------------------------------
// Inicia uma nova sessão de conversa (UC01)
// Chamado automaticamente quando a página abre.
// ------------------------------------------------------------
export async function iniciarSessao() {
  const resposta = await fetch(`${API_URL}/sessao/iniciar`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
  });
  if (!resposta.ok) throw new Error("Erro ao iniciar sessão");
  const dados = await resposta.json();
  return dados.sessao_id;
}

// ------------------------------------------------------------
// Envia uma pergunta e recebe a resposta do agente (RF01-RF05)
// ------------------------------------------------------------
export async function enviarPergunta(sessaoId, pergunta) {
  const resposta = await fetch(`${API_URL}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sessao_id: sessaoId, pergunta: pergunta }),
  });
  if (!resposta.ok) throw new Error("Erro ao enviar pergunta");
  return await resposta.json(); // { mensagem_id, resposta, fontes }
}

// ------------------------------------------------------------
// Envia a avaliação (1-5) de uma resposta (RF09)
// ------------------------------------------------------------
export async function enviarFeedback(mensagemId, nota) {
  const resposta = await fetch(`${API_URL}/feedback`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mensagem_id: mensagemId, nota: nota }),
  });
  if (!resposta.ok) throw new Error("Erro ao enviar feedback");
  return await resposta.json();
}

// ------------------------------------------------------------
// Encerra a sessão e descarta o histórico (RF07)
// ------------------------------------------------------------
export async function encerrarSessao(sessaoId) {
  const resposta = await fetch(`${API_URL}/sessao/encerrar`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sessao_id: sessaoId }),
  });
  if (!resposta.ok) throw new Error("Erro ao encerrar sessão");
  return await resposta.json();
}
