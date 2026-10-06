// ============================================================
// ListaMensagens.jsx - A área central com todas as mensagens
// ============================================================
// Recebe a lista de mensagens e as mostra em ordem. Depois de
// cada resposta do agente, mostra o componente de Feedback.
// ============================================================

import Mensagem from "./Mensagem";
import Feedback from "./Feedback";

// Sugestões de perguntas para a tela de boas-vindas
const SUGESTOES = [
  "O que são pensamentos automáticos?",
  "O que é a tríade cognitiva?",
  "O que são distorções cognitivas?",
  "Como funciona a reestruturação cognitiva?",
];

function ListaMensagens({ mensagens, carregando, onAvaliar, refFim, onSugestao }) {
  // mostra a tela de boas-vindas quando só há a mensagem inicial do agente
  const mostrarBoasVindas = mensagens.length <= 1;

  return (
    <div className="lista-mensagens">
      {mensagens.map((msg, indice) => (
        <div key={indice}>
          <Mensagem papel={msg.papel} texto={msg.texto} fontes={msg.fontes} />
          {msg.papel === "agente" && msg.mensagemId && (
            <Feedback mensagemId={msg.mensagemId} onAvaliar={onAvaliar} />
          )}
        </div>
      ))}

      {/* Tela de boas-vindas com sugestões de perguntas */}
      {mostrarBoasVindas && !carregando && (
        <div className="boas-vindas">
          <div className="boas-vindas-titulo">Como posso te ajudar hoje?</div>
          <div className="boas-vindas-sub">
            Escolha uma pergunta ou digite a sua:
          </div>
          <div className="sugestoes">
            {SUGESTOES.map((s, i) => (
              <button key={i} className="sugestao" onClick={() => onSugestao(s)}>
                {s}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Indicador "digitando" animado */}
      {carregando && (
        <div className="mensagem mensagem-agente">
          <div className="nome-agente">PsicoBot</div>
          <div className="balao balao-digitando">
            <span className="ponto"></span>
            <span className="ponto"></span>
            <span className="ponto"></span>
          </div>
        </div>
      )}

      <div ref={refFim} />
    </div>
  );
}

export default ListaMensagens;
