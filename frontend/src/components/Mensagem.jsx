// ============================================================
// Mensagem.jsx - Um balão de mensagem (do usuário ou do agente)
// ============================================================
// Recebe o "papel" (usuario ou agente) e o texto, e mostra o
// balão no estilo certo (alinhado à direita ou à esquerda).
// ============================================================

function Mensagem({ papel, texto, fontes }) {
  const ehUsuario = papel === "usuario";
  const classe = ehUsuario ? "mensagem mensagem-usuario" : "mensagem mensagem-agente";

  return (
    <div className={classe}>
      {!ehUsuario && <div className="nome-agente">PsicoBot</div>}
      <div className="balao">{texto}</div>

      {/* mostra as fontes consultadas (rastreabilidade) */}
      {!ehUsuario && fontes && fontes.length > 0 && (
        <div className="fontes">
          <span className="fontes-titulo">Fontes consultadas:</span>
          {fontes.map((f, i) => (
            <span key={i} className="fonte-item">
              {f.titulo} (similaridade {f.similaridade})
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

export default Mensagem;