from sqlalchemy import create_engine
import os

DB_SERVER = os.getenv("DB_SERVER")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

DB_SISCOB = "SISCOB"

connection_string = f"mssql+pyodbc://{DB_USER}:{DB_PASSWORD}@{DB_SERVER}/{DB_SISCOB}?driver=ODBC+Driver+17+for+SQL+Server"

engine_siscob = create_engine(connection_string)