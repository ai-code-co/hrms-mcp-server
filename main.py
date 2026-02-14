import os
import sys
import httpx
from fastmcp import FastMCP
import asyncpg
from dotenv import load_dotenv
import asyncio

load_dotenv()

# Only public config in .env
BASE_URL = os.getenv("HRMS_API_BASE_URL", "https://hrms-backend-1-m8ml.onrender.com")
DATABASE_URL = os.getenv("DATABASE_URL")

mcp = FastMCP(name="HRMS Per-User Server")

# --- DATABASE HELPER ---

async def get_db_connection():
    return await asyncpg.connect(DATABASE_URL)

async def init_db():
    """Each user gets their own row identified by their username."""
    conn = await get_db_connection()
    try:
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS user_sessions (
                username TEXT PRIMARY KEY,
                access_token TEXT,
                refresh_token TEXT
            )
        ''')
    finally:
        await conn.close()

# --- TOKEN LOGIC ---

async def save_user_tokens(username: str, access: str, refresh: str):
    conn = await get_db_connection()
    try:
        await conn.execute('''
            INSERT INTO user_sessions (username, access_token, refresh_token)
            VALUES ($1, $2, $3)
            ON CONFLICT (username) DO UPDATE 
            SET access_token = EXCLUDED.access_token, 
                refresh_token = EXCLUDED.refresh_token
        ''', username, access, refresh)
    finally:
        await conn.close()

async def get_user_tokens(username: str):
    conn = await get_db_connection()
    try:
        return await conn.fetchrow('SELECT access_token, refresh_token FROM user_sessions WHERE username = $1', username)
    finally:
        await conn.close()

async def refresh_user_token(username: str, refresh_token: str):
    """Attempts to refresh a specific user's token."""
    url = f"{BASE_URL}/api/auth/refresh-token/" 
    async with httpx.AsyncClient() as client:
        try:
            r = await client.post(url, json={"refresh": refresh_token})
            if r.status_code == 200:
                data = r.json()
                new_access = data.get("access")
                new_refresh = data.get("refresh", refresh_token)
                await save_user_tokens(username, new_access, new_refresh)
                return new_access
        except:
            return None
    return None

# --- THE AUTH TOOL ---

@mcp.tool()
async def login_to_hrms(username: str, password: str) -> str:
    """
    Authenticate with the HRMS. This is required before using other tools.
    Your credentials are used to get a secure session token.
    """
    url = f"{BASE_URL}/auth/login/"
    payload = {"username": username, "password": password}
    
    async with httpx.AsyncClient() as client:
        try:
            r = await client.post(url, json=payload)
            if r.status_code == 200:
                data = r.json()
                # Adjust keys based on your actual API response
                access = data.get("access") or data.get("token")
                refresh = data.get("refresh")
                
                await save_user_tokens(username, access, refresh)
                return f"Successfully logged in as {username}. You can now access your HRMS tools."
            else:
                return f"Login failed: {r.status_code} - {r.text}"
        except Exception as e:
            return f"Connection error: {str(e)}"

# --- REQUEST WRAPPER ---

async def authenticated_request(username: str, method: str, endpoint: str, params: dict = None, json_body: dict = None):
    """Handles logic for a specific user, including auto-refresh."""
    tokens = await get_user_tokens(username)
    if not tokens:
        return None, "Not logged in. Please use the login_to_hrms tool first."

    access_token = tokens['access_token']
    url = f"{BASE_URL}{endpoint}"
    
    async with httpx.AsyncClient(timeout=15.0) as client:
        headers = {"Authorization": f"Bearer {access_token}"}
        resp = await client.request(method, url, headers=headers, params=params, json=json_body)
        
        # If expired, try refresh
        if resp.status_code == 401 and tokens['refresh_token']:
            new_access = await refresh_user_token(username, tokens['refresh_token'])
            if new_access:
                headers = {"Authorization": f"Bearer {new_access}"}
                resp = await client.request(method, url, headers=headers, params=params, json=json_body)
        
        return resp, None

# --- BUSINESS TOOLS ---

@mcp.tool()
async def get_my_salary(username: str) -> str:
    """Get current user's salary information. Requires username."""
    resp, error = await authenticated_request(username, "GET", "/employees/me/salary-info/")
    if error: return error
    
    if resp.status_code == 200:
        return f"Salary Info for {username}: {resp.text}"
    return f"Error: {resp.status_code} {resp.text}"

@mcp.tool()
async def list_employees(username: str) -> str:
    """Admin Tool: Get list of all active employees. Requires admin username."""
    resp, error = await authenticated_request(username, "GET", "/api/employees/")
    if error: return error

    if resp.status_code == 200:
        return f"Employee List: {resp.text}"
    return f"Error: {resp.status_code} {resp.text}"

# --- MAIN ---

def main():
    try:
        asyncio.run(init_db())
    except Exception as e:
        print(f"[WARN] init_db failed: {e}", file=sys.stderr)
    
    port = int(os.getenv("PORT", 8000))
    print(f"[HRMS Server] Running on port {port}...", file=sys.stderr)
    mcp.run(transport="sse", host="0.0.0.0", port=port)

if __name__ == "__main__":
    main()