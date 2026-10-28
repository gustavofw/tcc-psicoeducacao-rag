"""Compara o embedder ONNX com o SentenceTransformers (devem ser iguais)."""
import numpy as np
from sentence_transformers import SentenceTransformer
from app.services.embedder_onnx import EmbedderONNX

FRASES = [
    "O que são pensamentos automáticos?",
    "triade cognitiva",
    "Qual a diferença entre crença central e crença intermediária?",
    "fale sobre star wars",
    "A terapia cognitivo-comportamental é uma abordagem estruturada, " * 20,  # texto longo (truncamento)
]

st = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
onnx_emb = EmbedderONNX()

for frase in FRASES:
    a = st.encode(frase)
    b = np.array(onnx_emb.embed(frase))
    cos = np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
    print(f"{cos:.4f} | {frase[:50]}")