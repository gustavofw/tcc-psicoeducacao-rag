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
      <div className="logo-area">
        <div className="logo-icone">P</div>
        <div>
          <div className="logo-nome">PsicoBot</div>
          <div className="logo-sub">Psicoeducação em TCC</div>
        </div>
      </div>

      <button className="botao-nova-conversa" onClick={onNovaConversa}>
        + Nova Conversa
      </button>

      <div className="historico">
        <span className="historico-titulo">Histórico (sessão)</span>
        <div className="historico-item">Conversa atual</div>
        <div className="historico-aviso">— sem persistência —</div>
      </div>

      {/* Aviso ético fixo no rodapé da barra lateral */}
      <div className="aviso-etico">
        <div className="aviso-etico-titulo">⚠️ Importante</div>
        <p>
          Este sistema oferece orientação educativa e <strong>não substitui</strong> o
          acompanhamento de um profissional de saúde mental.
        </p>
        <div className="aviso-contatos">
          Em caso de crise: <strong>CVV 188</strong> (24h)
        </div>
      </div>
    </div>
  );
}

export default BarraLateral;