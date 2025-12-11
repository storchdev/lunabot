import sqlite3
import psycopg2
from psycopg2 import sql

postgres_conn_info = "dbname='lunabot' user='lunabot' password='' host='localhost' port='5432'"

# connect to postgres
conn = psycopg2.connect(postgres_conn_info)
cur = conn.cursor()

with open('lunabotfinal.sql') as f:
    sql = f.read()
    for statement in sql.split(';\n'):
        if not statement:
            continue
        try:
            cur.execute(statement)
        except Exception as e:
            print(e)
            print(statement)
            break
    conn.commit()

conn.close()

