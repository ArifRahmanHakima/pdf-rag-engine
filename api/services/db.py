import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

def get_postgres_conn():
    sslmode = os.getenv("POSTGRES_SSLMODE", "disable")
    conn_params = {
        "dbname": os.getenv("POSTGRES_DB"),
        "user": os.getenv("POSTGRES_USER"),
        "password": os.getenv("POSTGRES_PASSWORD"),
        "host": os.getenv("POSTGRES_HOST"),
        "port": os.getenv("POSTGRES_PORT"),
        "cursor_factory": RealDictCursor
    }
    
    # Add sslmode for Neon (production)
    if sslmode == "require":
        conn_params["sslmode"] = "require"
    
    return psycopg2.connect(**conn_params)
