"""Gera embeddings com onnxruntime + sentencepiece (baixo consumo de memória)."""
from pathlib import Path

import numpy as np
import onnxruntime as ort
import sentencepiece as spm

PASTA_MODELO = Path(__file__).resolve().parents[2] / "modelo_onnx"  # backend/modelo_onnx
MAX_TOKENS_EMBEDDING = 128  # mesmo limite do SentenceTransformers para este modelo
BOS, EOS = 0, 2             # <s> e </s>


class EmbedderONNX:
    def __init__(self, pasta=PASTA_MODELO):
        opcoes = ort.SessionOptions()
        opcoes.graph_optimization_level = ort.GraphOptimizationLevel.ORT_DISABLE_ALL
        opcoes.enable_cpu_mem_arena = False
        opcoes.intra_op_num_threads = 1
        opcoes.inter_op_num_threads = 1
        opcoes.add_session_config_entry("session.disable_prepacking", "1")
        self.sessao = ort.InferenceSession(
            str(pasta / "model.onnx"), sess_options=opcoes,
            providers=["CPUExecutionProvider"],
        )
        self.entradas = {e.name for e in self.sessao.get_inputs()}
        saidas = [s.name for s in self.sessao.get_outputs()]
        self.saida = "last_hidden_state" if "last_hidden_state" in saidas else saidas[0]
        self.tokenizador = spm.SentencePieceProcessor(model_file=str(pasta / "tokenizer.spm"))

    def embed(self, texto):
        pecas = self.tokenizador.encode(texto)[: MAX_TOKENS_EMBEDDING - 2]
        ids = np.array([[BOS] + pecas + [EOS]], dtype=np.int64)
        mascara = np.ones_like(ids)
        entrada = {"input_ids": ids, "attention_mask": mascara}
        if "token_type_ids" in self.entradas:
            entrada["token_type_ids"] = np.zeros_like(ids)

        tokens = self.sessao.run([self.saida], entrada)[0]  # [1, n_tokens, 384]
        # Mean pooling (igual ao SentenceTransformers)
        m = mascara[..., None].astype(np.float32)
        vetor = (tokens * m).sum(axis=1) / np.clip(m.sum(axis=1), 1e-9, None)
        return vetor[0].tolist()