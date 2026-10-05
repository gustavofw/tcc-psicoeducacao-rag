// ============================================================
// App.jsx - A tela principal (junta todos os componentes)
// ============================================================
// Aqui fica a "inteligência" do front-end:
//  - guarda o estado (sessão, mensagens, carregando)
//  - inicia a sessão quando a página abre
//  - envia perguntas e recebe respostas da API
//  - envia o feedback
// ============================================================

import { useState, useEffect } from "react";
import BarraLateral from "./components/BarraLateral";
import ListaMensagens from "./components/ListaMensagens";
import CampoEntrada from "./components/CampoEntrada";
import { iniciarSessao, enviarPergunta, enviarFeedback, encerrarSessao } from "./api";
import "./App.css";

function App() {
  // --- ESTADOS (a "memória" da tela) ---
  const [sessaoId, setSessaoId] = useState(null);   // id da sessão atual
  const [mensagens, setMensagens] = useState([]);   // lista de mensagens na tela
  const [carregando, setCarregando] = useState(false); // se está esperando o agente

  // --- Ao abrir a página, inicia a sessão automaticamente (UC01) ---
  useEffect(() => {
    async function comecar() {
      try {
        const id = await iniciarSessao();
        setSessaoId(id);
        // mensagem de boas-vindas do agente
        setMensagens([
          {
            papel: "agente",
            texto:
              "Olá! Sou o PsicoBot. Posso explicar conceitos da Terapia Cognitivo-Comportamental. Como posso ajudar?",
            mensagemId: null, // boas-vindas não recebe feedback
          },
        ]);
      } catch (erro) {
        console.error(erro);
        alert("Não consegui conectar ao servidor. Verifique se a API está rodando.");
      }
    }
    comecar();
  }, []); // [] = roda só uma vez, quando a página abre

  // --- Enviar uma pergunta ---
  async function aoEnviar(pergunta) {
    // 1. adiciona a mensagem do usuário na tela imediatamente
    setMensagens((atual) => [...atual, { papel: "usuario", texto: pergunta }]);
    setCarregando(true);

    try {
      // 2. chama a API (isso pode demorar por causa do Llama local)
      const dados = await enviarPergunta(sessaoId, pergunta);

      // 3. adiciona a resposta do agente na tela
      setMensagens((atual) => [
        ...atual,
        {
          papel: "agente",
          texto: dados.resposta,
          mensagemId: dados.mensagem_id, // guarda o id para o feedback
        },
      ]);
    } catch (erro) {
      console.error(erro);
      setMensagens((atual) => [
        ...atual,
        { papel: "agente", texto: "Desculpe, ocorreu um erro. Tente novamente.", mensagemId: null },
      ]);
    } finally {
      setCarregando(false);
    }
  }

  // --- Enviar o feedback (RF09) ---
  async function aoAvaliar(mensagemId, nota) {
    try {
      await enviarFeedback(mensagemId, nota);
    } catch (erro) {
      console.error(erro);
    }
  }

  // --- Nova conversa (encerra a atual e inicia outra) ---
  async function aoNovaConversa() {
    try {
      if (sessaoId) await encerrarSessao(sessaoId); // RF07
      const novoId = await iniciarSessao();
      setSessaoId(novoId);
      setMensagens([
        {
          papel: "agente",
          texto: "Nova conversa iniciada. Como posso ajudar?",
          mensagemId: null,
        },
      ]);
    } catch (erro) {
      console.error(erro);
    }
  }

  return (
    <div className="app">
      <BarraLateral onNovaConversa={aoNovaConversa} />

      <div className="area-chat">
        <div className="cabecalho">
          <div className="avatar">P</div>
          <div>
            <div className="cabecalho-nome">PsicoBot</div>
            <div className="cabecalho-sub">Orientação psicoeducativa baseada em TCC</div>
          </div>
        </div>

        <ListaMensagens
          mensagens={mensagens}
          carregando={carregando}
          onAvaliar={aoAvaliar}
        />

        <CampoEntrada onEnviar={aoEnviar} desabilitado={carregando || !sessaoId} />
      </div>
    </div>
  );
}

export default App;
