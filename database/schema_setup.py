from .connection import get_db_connection
async def init_db():
    conn = await get_db_connection()
    try:
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS user_sessions (
                session_id TEXT PRIMARY KEY,
                access_token TEXT,
                refresh_token TEXT
            )
        ''')
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS pairing_codes (
                code TEXT PRIMARY KEY,
                access_token TEXT,
                refresh_token TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
    finally:
        await conn.close()