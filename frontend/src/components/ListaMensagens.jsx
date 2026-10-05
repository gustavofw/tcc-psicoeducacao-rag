// ============================================================
// ListaMensagens.jsx - A área central com todas as mensagens
// ============================================================
// Recebe a lista de mensagens e as mostra em ordem. Depois de
// cada resposta do agente, mostra o componente de Feedback.
// ============================================================

import Mensagem from "./Mensagem";
import Feedback from "./Feedback";

function ListaMensagens({ mensagens, carregando, onAvaliar }) {
  return (
    <div className="lista-mensagens">
      {mensagens.map((msg, indice) => (
        <div key={indice}>
          <Mensagem papel={msg.papel} texto={msg.texto} />

          {/* Se for resposta do agente e tiver id, mostra o feedback */}
          {msg.papel === "agente" && msg.mensagemId && (
            <Feedback mensagemId={msg.mensagemId} onAvaliar={onAvaliar} />
          )}
        </div>
      ))}

      {/* Indicador de "digitando..." enquanto o Llama gera a resposta */}
      {carregando && (
        <div className="mensagem mensagem-agente">
          <div className="nome-agente">PsicoBot</div>
          <div className="balao balao-carregando">Pensando...</div>
        </div>
      )}
    </div>
  );
}

export default ListaMensagens;
