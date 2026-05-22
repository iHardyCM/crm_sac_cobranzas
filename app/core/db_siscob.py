from urllib.parse import quote_plus

from dotenv import load_dotenv
from sqlalchemy import create_engine
import os


load_dotenv()

DB_SERVER = os.getenv("DB_SERVER")
DB_NAME = os.getenv("DB_NAME", "CobAuto")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_DRIVER = os.getenv("DB_DRIVER", "ODBC Driver 17 for SQL Server")


connection_string = (
    f"DRIVER={{{DB_DRIVER}}};"
    f"SERVER={DB_SERVER};"
    f"DATABASE={DB_NAME};"
    f"UID={DB_USER};"
    f"PWD={DB_PASSWORD};"
    "Encrypt=no;"
    "TrustServerCertificate=yes;"
)


engine_siscob = create_engine(
    f"mssql+pyodbc:///?odbc_connect={quote_plus(connection_string)}",
    pool_pre_ping=True
)

