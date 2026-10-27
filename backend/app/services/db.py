"""Conexão com o banco de dados PostgreSQL."""
import psycopg2
from app.core.config import DB_CONFIG, DATABASE_URL

def get_conexao():
    """Abre e retorna uma conexão com o banco (Neon se DATABASE_URL existir)."""
    if DATABASE_URL:
        return psycopg2.connect(DATABASE_URL)
    return psycopg2.connect(**DB_CONFIG)