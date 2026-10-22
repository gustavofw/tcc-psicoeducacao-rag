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
            <div key={i} className="fonte-item">
              <span className="fonte-cabecalho">
                {i + 1}. {f.titulo} (similaridade {f.similaridade})
              </span>
              <span className="fonte-trecho">"{f.conteudo}"</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default Mensagem;