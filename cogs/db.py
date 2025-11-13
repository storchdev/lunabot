import asyncpg
from config import DB_LOGIN


async def init_db():
    pool = await asyncpg.create_pool(
        user="awd_bot",
        database="awd_bot",
        password=DB_LOGIN,
        host="localhost",
        port="5432",
    )
    with open("schema.sql") as f:
        await pool.execute(f.read())
    return pool
