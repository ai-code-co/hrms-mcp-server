from database.connection import get_db_connection

async def link_account_with_code(sync_code: str) -> str:
    """Finish the connection process using the 6-digit sync code."""
    conn = await get_db_connection()
    row = await conn.fetchrow("DELETE FROM pairing_codes WHERE code = $1 RETURNING access_token, refresh_token", sync_code)
    if row:
        await conn.execute("INSERT INTO user_sessions (session_id, access_token, refresh_token) VALUES ('default', $1, $2) "
                         "ON CONFLICT (session_id) DO UPDATE SET access_token=$1, refresh_token=$2", 
                         row['access_token'], row['refresh_token'])
        await conn.close()
        return "Account successfully linked. I can now assist you with your HR data."
    await conn.close()
    return "Invalid or expired code."