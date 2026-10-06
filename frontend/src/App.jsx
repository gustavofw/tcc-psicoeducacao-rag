// ============================================================
// App.jsx - A tela principal (junta todos os componentes)
// ============================================================

import { useState, useEffect, useRef } from "react";
import BarraLateral from "./components/BarraLateral";
import ListaMensagens from "./components/ListaMensagens";
import CampoEntrada from "./components/CampoEntrada";
import { iniciarSessao, enviarPergunta, enviarFeedback, encerrarSessao } from "./api";
import "./App.css";

function App() {
  // --- ESTADOS (a "memória" da tela) ---
  const [sessaoId, setSessaoId] = useState(null);
  const [mensagens, setMensagens] = useState([]);
  const [carregando, setCarregando] = useState(false);

  // referência para o fim da lista (usada no scroll automático)
  const fimDasMensagens = useRef(null);

  // rola automaticamente para a última mensagem sempre que a lista muda
  useEffect(() => {
    fimDasMensagens.current?.scrollIntoView({ behavior: "smooth" });
  }, [mensagens, carregando]);

  // --- Ao abrir a página, inicia a sessão automaticamente (UC01) ---
  useEffect(() => {
    async function comecar() {
      try {
        const id = await iniciarSessao();
        setSessaoId(id);
        setMensagens([
          {
            papel: "agente",
            texto:
              "Olá! Sou o PsicoBot. Posso explicar conceitos da Terapia Cognitivo-Comportamental. Como posso ajudar?",
            mensagemId: null,
          },
        ]);
      } catch (erro) {
        console.error(erro);
        alert("Não consegui conectar ao servidor. Verifique se a API está rodando.");
      }
    }
    comecar();
  }, []);

  // --- Enviar uma pergunta ---
  async function aoEnviar(pergunta) {
    setMensagens((atual) => [...atual, { papel: "usuario", texto: pergunta }]);
    setCarregando(true);

    try {
      const dados = await enviarPergunta(sessaoId, pergunta);
      setMensagens((atual) => [
        ...atual,
        {
          papel: "agente",
          texto: dados.resposta,
          mensagemId: dados.mensagem_id,
          fontes: dados.fontes, // guarda as fontes para exibir na tela
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
      if (sessaoId) await encerrarSessao(sessaoId);
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
          refFim={fimDasMensagens}
        />

        <CampoEntrada onEnviar={aoEnviar} desabilitado={carregando || !sessaoId} />
      </div>
    </div>
  );
}

export default App;