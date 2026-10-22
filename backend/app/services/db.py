"""Conexão com o banco de dados PostgreSQL."""
import psycopg2
from app.core.config import DB_CONFIG

def get_conexao():
    """Abre e retorna uma conexão com o banco."""
    return psycopg2.connect(**DB_CONFIG)