// ============================================================
// Feedback.jsx - Componente de avaliação 1 a 5 (RF09)
// ============================================================
// Mostra os botões de 1 a 5 abaixo de uma resposta do agente.
// Quando o usuário clica, chama a função onAvaliar (que envia
// para a API) e marca a nota escolhida.
// ============================================================

import { useState } from "react";

function Feedback({ mensagemId, onAvaliar }) {
  // guarda a nota que o usuário escolheu (null = ainda não avaliou)
  const [notaEscolhida, setNotaEscolhida] = useState(null);

  function avaliar(nota) {
    setNotaEscolhida(nota);      // marca visualmente
    onAvaliar(mensagemId, nota); // envia para a API
  }

  return (
    <div className="feedback">
      <span className="feedback-pergunta">Esta resposta foi útil?</span>
      <div className="feedback-notas">
        {[1, 2, 3, 4, 5].map((nota) => (
          <button
            key={nota}
            className={
              "feedback-botao" + (notaEscolhida === nota ? " feedback-selecionado" : "")
            }
            onClick={() => avaliar(nota)}
            disabled={notaEscolhida !== null} // trava após avaliar
          >
            {nota}
          </button>
        ))}
      </div>
      {notaEscolhida !== null && (
        <span className="feedback-obrigado">Obrigado pelo feedback!</span>
      )}
    </div>
  );
}

export default Feedback;
