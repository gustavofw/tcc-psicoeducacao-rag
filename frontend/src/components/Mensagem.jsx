// ============================================================
// Mensagem.jsx - Um balão de mensagem (do usuário ou do agente)
// ============================================================
// Recebe o "papel" (usuario ou agente) e o texto, e mostra o
// balão no estilo certo (alinhado à direita ou à esquerda).
// ============================================================

function Mensagem({ papel, texto }) {
  // define a classe CSS conforme quem enviou
  const ehUsuario = papel === "usuario";
  const classe = ehUsuario ? "mensagem mensagem-usuario" : "mensagem mensagem-agente";

  return (
    <div className={classe}>
      {!ehUsuario && <div className="nome-agente">PsicoBot</div>}
      <div className="balao">{texto}</div>
    </div>
  );
}

export default Mensagem;
