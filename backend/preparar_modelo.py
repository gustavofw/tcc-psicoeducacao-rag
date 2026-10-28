"""
Baixa o modelo ONNX (o mesmo usado pelo fastembed) e salva os pesos
em arquivo separado (external data), para o onnxruntime ler direto
do disco (memory-mapped) e caber nos 512 MB da Render.
"""
import shutil
from pathlib import Path
import onnx
from huggingface_hub import snapshot_download

REPO = "Qdrant/paraphrase-multilingual-MiniLM-L12-v2-onnx-Q"
DESTINO = Path(__file__).resolve().parent / "modelo_onnx"


def main():
    print(f"Baixando {REPO}...")
    origem = Path(snapshot_download(REPO, allow_patterns=["*.onnx", "*.json"]))
    DESTINO.mkdir(exist_ok=True)

    print("Convertendo para pesos em arquivo separado...")
    modelo = onnx.load(str(origem / "model_optimized.onnx"))
    onnx.save_model(
        modelo,
        str(DESTINO / "model.onnx"),
        save_as_external_data=True,
        all_tensors_to_one_file=True,
        location="model.onnx.data",
        size_threshold=1024,
    )
    shutil.copy(origem / "tokenizer.json", DESTINO / "tokenizer.json")
    print(f"Modelo pronto em {DESTINO}")


if __name__ == "__main__":
    main()