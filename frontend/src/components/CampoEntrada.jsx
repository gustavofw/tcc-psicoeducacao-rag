// ============================================================
// CampoEntrada.jsx - Caixa de texto + botão de enviar
// ============================================================
// Guarda o texto que o usuário está digitando e, ao enviar,
// chama a função onEnviar (que a tela principal passa).
// ============================================================

import { useState } from "react";

function CampoEntrada({ onEnviar, desabilitado }) {
  const [texto, setTexto] = useState("");

  function enviar() {
    const limpo = texto.trim();
    if (limpo === "") return;   // não envia vazio
    onEnviar(limpo);            // manda para a tela principal
    setTexto("");               // limpa o campo
  }

  // permite enviar apertando Enter (Shift+Enter quebra linha)
  function aoTeclar(evento) {
    if (evento.key === "Enter" && !evento.shiftKey) {
      evento.preventDefault();
      enviar();
    }
  }

  return (
    <div className="campo-entrada">
      <textarea
        className="campo-texto"
        placeholder="Digite sua mensagem..."
        value={texto}
        onChange={(e) => setTexto(e.target.value)}
        onKeyDown={aoTeclar}
        disabled={desabilitado}
        rows={1}
      />
      <button className="botao-enviar" onClick={enviar} disabled={desabilitado}>
        →
      </button>
    </div>
  );
}

export default CampoEntrada;
