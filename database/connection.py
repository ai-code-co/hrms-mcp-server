import asyncpg
import os

async def get_db_connection():
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set")
    return await asyncpg.connect(database_url)
