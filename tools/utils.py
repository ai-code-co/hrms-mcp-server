import httpx
import os
from database.connection import get_db_connection

BASE_URL = os.getenv("HRMS_API_BASE_URL", "https://hrms-backend-1-m8ml.onrender.com").rstrip("/")

async def refresh_tokens(session_id: str, refresh_token: str):
    url = f"{BASE_URL}/api/auth/token/refresh/"
    async with httpx.AsyncClient() as client:
        r = await client.post(url, json={"refresh": refresh_token})
        if r.status_code == 200:
            new_data = r.json()
            conn = await get_db_connection()
            await conn.execute("UPDATE user_sessions SET access_token=$1 WHERE session_id=$2", new_data['access'], session_id)
            await conn.close()
            return new_data['access']
    return None


async def hrms_api_call(endpoint: str, method="GET", params=None, json_data=None):
    conn = await get_db_connection()
    tokens = await conn.fetchrow("SELECT access_token, refresh_token FROM user_sessions WHERE session_id = 'default'")
    await conn.close()

    if not tokens:
        return "Not connected. Please use the 'get_connection_link' tool first."

    async with httpx.AsyncClient(timeout=20.0) as client:
        headers = {"Authorization": f"Bearer {tokens['access_token']}"}
        resp = await client.request(
            method,
            f"{BASE_URL}{endpoint}",
            headers=headers,
            params=params,
            json=json_data,
        )
        
        if resp.status_code == 401: # Expired
            new_access = await refresh_tokens('default', tokens['refresh_token'])
            if new_access:
                headers["Authorization"] = f"Bearer {new_access}"
                resp = await client.request(
                    method,
                    f"{BASE_URL}{endpoint}",
                    headers=headers,
                    params=params,
                    json=json_data,
                )
        
        return resp.text
    
    
