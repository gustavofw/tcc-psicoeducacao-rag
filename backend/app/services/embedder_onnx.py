"""Gera embeddings com onnxruntime (pesos memory-mapped, pouca memória)."""
from pathlib import Path
import numpy as np
import onnxruntime as ort
from tokenizers import Tokenizer

PASTA_MODELO = Path(__file__).resolve().parents[2] / "modelo_onnx"  # backend/modelo_onnx
MAX_TOKENS_EMBEDDING = 128  # mesmo limite do SentenceTransformers para este modelo


class EmbedderONNX:
    def __init__(self, pasta=PASTA_MODELO):
        opcoes = ort.SessionOptions()
        # O modelo já vem otimizado; desligar a otimização evita cópias dos pesos
        opcoes.graph_optimization_level = ort.GraphOptimizationLevel.ORT_DISABLE_ALL
        opcoes.enable_cpu_mem_arena = False
        opcoes.intra_op_num_threads = 1
        opcoes.inter_op_num_threads = 1
        self.sessao = ort.InferenceSession(
            str(pasta / "model.onnx"), sess_options=opcoes,
            providers=["CPUExecutionProvider"],
        )
        self.entradas = {e.name for e in self.sessao.get_inputs()}
        saidas = [s.name for s in self.sessao.get_outputs()]
        self.saida = "last_hidden_state" if "last_hidden_state" in saidas else saidas[0]

        self.tokenizador = Tokenizer.from_file(str(pasta / "tokenizer.json"))
        self.tokenizador.enable_truncation(max_length=MAX_TOKENS_EMBEDDING)
        self.tokenizador.no_padding()

    def embed(self, texto):
        cod = self.tokenizador.encode(texto)
        ids = np.array([cod.ids], dtype=np.int64)
        mascara = np.array([cod.attention_mask], dtype=np.int64)
        entrada = {"input_ids": ids, "attention_mask": mascara}
        if "token_type_ids" in self.entradas:
            entrada["token_type_ids"] = np.zeros_like(ids)

        tokens = self.sessao.run([self.saida], entrada)[0]  # [1, n_tokens, 384]
        # Mean pooling (igual ao SentenceTransformers)
        m = mascara[..., None].astype(np.float32)
        vetor = (tokens * m).sum(axis=1) / np.clip(m.sum(axis=1), 1e-9, None)
        return vetor[0].tolist()