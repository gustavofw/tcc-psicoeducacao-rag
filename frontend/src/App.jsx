// ============================================================
// App.jsx - A tela principal (junta todos os componentes)
// ============================================================

import { useState, useEffect, useRef } from "react";
import BarraLateral from "./components/BarraLateral";
import ListaMensagens from "./components/ListaMensagens";
import CampoEntrada from "./components/CampoEntrada";
import { iniciarSessao, enviarPergunta, enviarFeedback, encerrarSessao, validarAcesso } from "./api";
import "./App.css";

function App() {
  // --- ESTADOS (a "memória" da tela) ---
  const [sessaoId, setSessaoId] = useState(null);
  const [mensagens, setMensagens] = useState([]);
  const [carregando, setCarregando] = useState(false);
  const [acessoLiberado, setAcessoLiberado] = useState(false);
  const [codigoDigitado, setCodigoDigitado] = useState("");
  const [erroAcesso, setErroAcesso] = useState("");

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

  async function aoValidarCodigo(e) {
    e.preventDefault();
    const valido = await validarAcesso(codigoDigitado);
    if (valido) {
      setAcessoLiberado(true);
      setErroAcesso("");
    } else {
      setErroAcesso("Código inválido. Verifique e tente novamente.");
    }
  }

    // Tela de código de acesso (só avaliadores)
  if (!acessoLiberado) {
    return (
      <div className="tela-acesso">
        <div className="caixa-acesso">
          <h2>PsicoBot</h2>
          <p>Protótipo acadêmico de psicoeducação em TCC.<br />
             Digite o código de acesso fornecido para avaliadores.</p>
          <form onSubmit={aoValidarCodigo}>
            <input
              type="password"
              value={codigoDigitado}
              onChange={(e) => setCodigoDigitado(e.target.value)}
              placeholder="Código de acesso"
            />
            <button type="submit">Entrar</button>
          </form>
          {erroAcesso && <p className="erro-acesso">{erroAcesso}</p>}
          <p className="aviso-acesso">
            Este é um protótipo de pesquisa e não substitui atendimento psicológico.
            Em caso de crise, ligue 188 (CVV).
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="app">
      <BarraLateral onNovaConversa={aoNovaConversa} />

      <div className="area-chat">
        <div className="cabecalho">
          <div className="cabecalho-info">
            <div className="cabecalho-nome">PsicoBot</div>
            <div className="cabecalho-sub">Orientação psicoeducativa baseada em TCC</div>
          </div>
          <div className="cabecalho-cvv">
            Em crise? <strong>CVV 188</strong> (24h)
          </div>
        </div>

        <ListaMensagens
          mensagens={mensagens}
          carregando={carregando}
          onAvaliar={aoAvaliar}
          refFim={fimDasMensagens}
          onSugestao={aoEnviar}
        />

        <CampoEntrada onEnviar={aoEnviar} desabilitado={carregando || !sessaoId} />
      </div>
    </div>
  );
}

export default App;