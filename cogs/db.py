import asyncpg
from config import DB_LOGIN


async def init_db():
    pool = await asyncpg.create_pool(
        user="lunabot",
        database="lunabot",
        password=DB_LOGIN,
        host="localhost",
        port="5432",
    )
    with open("schema.sql") as f:
        await pool.execute(f.read())
    return pool
