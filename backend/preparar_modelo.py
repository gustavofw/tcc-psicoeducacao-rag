"""
Prepara o modelo de embeddings para a Render (512 MB):
- baixa o modelo ONNX (Qdrant/paraphrase-multilingual-MiniLM-L12-v2-onnx-Q);
- converte os pesos de FP16 para FP32 e salva em arquivo separado
  (lidos do disco sob demanda, sem cópia em memória);
- gera um tokenizador sentencepiece a partir do mesmo vocabulário
  (o tokenizador do tokenizer.json ocupava ~280 MB de RAM).
"""
import base64
import json
from pathlib import Path

import numpy as np
import onnx
from huggingface_hub import snapshot_download
from onnx import TensorProto, numpy_helper
from sentencepiece import sentencepiece_model_pb2 as pb

REPO = "Qdrant/paraphrase-multilingual-MiniLM-L12-v2-onnx-Q"
DESTINO = Path(__file__).resolve().parent / "modelo_onnx"


def converter_modelo(origem):
    print("Convertendo pesos FP16 -> FP32 (arquivo separado)...")
    modelo = onnx.load(str(origem / "model_optimized.onnx"))
    for t in modelo.graph.initializer:
        if t.data_type == TensorProto.FLOAT16:
            arr = numpy_helper.to_array(t).astype(np.float32)
            t.CopyFrom(numpy_helper.from_array(arr, t.name))
    del modelo.graph.value_info[:]  # tipos intermediários eram FP16
    onnx.save_model(
        modelo,
        str(DESTINO / "model.onnx"),
        save_as_external_data=True,
        all_tensors_to_one_file=True,
        location="model.onnx.data",
        size_threshold=1024,
    )


def converter_tokenizador(origem):
    print("Gerando tokenizador sentencepiece...")
    tok = json.loads((origem / "tokenizer.json").read_text(encoding="utf-8"))
    m = pb.ModelProto()
    m.trainer_spec.model_type = pb.TrainerSpec.UNIGRAM
    m.trainer_spec.vocab_size = len(tok["model"]["vocab"])
    m.trainer_spec.bos_id, m.trainer_spec.pad_id = 0, 1
    m.trainer_spec.eos_id, m.trainer_spec.unk_id = 2, 3
    m.trainer_spec.split_by_whitespace = True
    m.trainer_spec.byte_fallback = False
    m.normalizer_spec.name = "nmt_nfkc"
    m.normalizer_spec.precompiled_charsmap = base64.b64decode(
        tok["normalizer"]["precompiled_charsmap"]
    )
    m.normalizer_spec.add_dummy_prefix = True
    m.normalizer_spec.remove_extra_whitespaces = True
    m.normalizer_spec.escape_whitespaces = True
    controle = {"<s>", "<pad>", "</s>", "<mask>"}
    for peca, score in tok["model"]["vocab"]:
        p = m.pieces.add()
        p.piece, p.score = peca, score
        if peca in controle:
            p.type = pb.ModelProto.SentencePiece.CONTROL
        elif peca == "<unk>":
            p.type = pb.ModelProto.SentencePiece.UNKNOWN
        else:
            p.type = pb.ModelProto.SentencePiece.NORMAL
    (DESTINO / "tokenizer.spm").write_bytes(m.SerializeToString())


def main():
    print(f"Baixando {REPO}...")
    origem = Path(snapshot_download(REPO, allow_patterns=["*.onnx", "*.json"]))
    DESTINO.mkdir(exist_ok=True)
    converter_modelo(origem)
    converter_tokenizador(origem)
    print(f"Modelo pronto em {DESTINO}")


if __name__ == "__main__":
    main()