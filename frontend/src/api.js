// ============================================================
// api.js - Funções que conversam com a API (back-end FastAPI)
// ============================================================
// Centraliza todas as chamadas à API num lugar só. Assim, se a
// URL do back-end mudar, você altera apenas aqui.
// ============================================================

// Endereço da sua API. Em desenvolvimento é localhost:8000.
// Em desenvolvimento usa localhost; em produção, a URL vem da variável de ambiente
const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

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
    body: JSON.stringify({
      sessao_id: sessaoId,
      pergunta: pergunta,
      codigo: codigoAcesso,   // envia o código junto
    }),
  });
  if (!resposta.ok) throw new Error("Erro ao enviar pergunta");
  return await resposta.json();
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

// guarda o código de acesso validado, para usar nas próximas chamadas
let codigoAcesso = "";

export async function validarAcesso(codigo) {
  const resposta = await fetch(`${API_URL}/validar-acesso`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ codigo }),
  });
  if (resposta.ok) {
    codigoAcesso = codigo;  // guarda para usar no /chat
  }
  return resposta.ok;
}