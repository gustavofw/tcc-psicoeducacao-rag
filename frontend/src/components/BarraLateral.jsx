// ============================================================
// BarraLateral.jsx - Barra lateral esquerda
// ============================================================
// Mostra o botão "Nova Conversa" e o histórico da sessão atual
// (sem persistência, conforme o RNF02). Ao clicar em Nova
// Conversa, chama onNovaConversa (que reinicia a sessão).
// ============================================================

function BarraLateral({ onNovaConversa }) {
  return (
    <div className="barra-lateral">
      <button className="botao-nova-conversa" onClick={onNovaConversa}>
        + Nova Conversa
      </button>

      <div className="historico">
        <span className="historico-titulo">Histórico (sessão)</span>
        <div className="historico-item">Conversa atual</div>
        <div className="historico-aviso">— sem persistência —</div>
      </div>
    </div>
  );
}

export default BarraLateral;
