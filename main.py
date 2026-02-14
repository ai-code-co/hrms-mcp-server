import os
import sys
import httpx
import secrets
import asyncio
import asyncpg
from fastmcp import FastMCP
from dotenv import load_dotenv
from fastapi import Request
from fastapi.responses import HTMLResponse

load_dotenv()

BASE_URL = os.getenv("HRMS_API_BASE_URL", "https://hrms-backend-1-m8ml.onrender.com")
DATABASE_URL = os.getenv("DATABASE_URL")
# The URL where this MCP server is hosted (e.g., https://mcp-server.onrender.com)
SERVER_URL = os.getenv("SERVER_URL", "http://localhost:8000") 

mcp = FastMCP(name="HRMS Secure Server")

# --- DATABASE ---

async def get_db_connection():
    return await asyncpg.connect(DATABASE_URL)

async def init_db():
    conn = await get_db_connection()
    try:
        # user_sessions: Stores actual tokens
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS user_sessions (
                session_id TEXT PRIMARY KEY,
                access_token TEXT,
                refresh_token TEXT
            )
        ''')
        # pairing_codes: Temporary table to link the web login to ChatGPT
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

# --- WEB UI (Bypasses ChatGPT Safety) ---

@mcp.custom_route("/login", methods=["GET"])
async def login_page(request: Request):
    """A simple login form hosted on the MCP server."""
    return HTMLResponse("""
    <html>
        <body>
            <h2>HRMS Login</h2>
            <form action="/login" method="post">
                <input type="text" name="username" placeholder="Username" required><br><br>
                <input type="password" name="password" placeholder="Password" required><br><br>
                <button type="submit">Login & Generate Code</button>
            </form>
        </body>
    </html>
    """)

@mcp.custom_route("/login", methods=["POST"])
async def handle_login(request: Request):
    """Validates credentials with HRMS and generates a pairing code."""
    form = await request.form()
    username = form.get("username")
    password = form.get("password")

    if not username or not password:
        return HTMLResponse(
            "<h1>Login Failed</h1><p>Missing username or password.</p><a href='/login'>Try again</a>",
            status_code=400
        )

    url = f"{BASE_URL}/auth/login/"
    async with httpx.AsyncClient() as client:
        r = await client.post(url, json={"username": username, "password": password})
        if r.status_code == 200:
            data = r.json()
            access = data.get("access") or data.get("token")
            refresh = data.get("refresh")
            
            # Generate a 6-digit pairing code
            pairing_code = "".join(secrets.choice("0123456789") for _ in range(6))
            
            conn = await get_db_connection()
            await conn.execute(
                "INSERT INTO pairing_codes (code, access_token, refresh_token) VALUES ($1, $2, $3)",
                pairing_code, access, refresh
            )
            await conn.close()
            
            return HTMLResponse(
                f"<h1>Success!</h1><p>Your pairing code is: <b>{pairing_code}</b></p><p>Copy this code and give it to ChatGPT.</p>"
            )
        else:
            return HTMLResponse(
                f"<h1>Login Failed</h1><p>{r.text}</p><a href='/login'>Try again</a>",
                status_code=r.status_code
            )

# --- TOOLS ---

@mcp.tool()
async def get_login_link() -> str:
    """Returns the URL where the user can safely log in to the HRMS."""
    return f"Please log in here: {SERVER_URL}/login\nAfter logging in, you will receive a 6-digit pairing code. Provide that code to me using the 'complete_auth' tool."

@mcp.tool()
async def complete_auth(pairing_code: str, session_name: str) -> str:
    """
    Finalize the authentication using the 6-digit code.
    'session_name' can be anything (e.g., your name) to identify this session.
    """
    conn = await get_db_connection()
    row = await conn.fetchrow("DELETE FROM pairing_codes WHERE code = $1 RETURNING access_token, refresh_token", pairing_code)
    
    if row:
        await conn.execute(
            "INSERT INTO user_sessions (session_id, access_token, refresh_token) VALUES ($1, $2, $3) "
            "ON CONFLICT (session_id) DO UPDATE SET access_token=EXCLUDED.access_token, refresh_token=EXCLUDED.refresh_token",
            session_name, row['access_token'], row['refresh_token']
        )
        await conn.close()
        return f"Authentication successful for session '{session_name}'. You can now use HRMS tools."
    
    await conn.close()
    return "Invalid or expired pairing code. Please generate a new one via the login link."

# --- AUTHENTICATED REQUEST HELPER ---

async def hrms_api_call(session_name: str, method: str, endpoint: str, params=None):
    conn = await get_db_connection()
    tokens = await conn.fetchrow("SELECT access_token, refresh_token FROM user_sessions WHERE session_id = $1", session_name)
    await conn.close()

    if not tokens:
        return f"Error: No active session found for '{session_name}'. Please login first."

    async with httpx.AsyncClient() as client:
        headers = {"Authorization": f"Bearer {tokens['access_token']}"}
        resp = await client.request(method, f"{BASE_URL}{endpoint}", headers=headers, params=params)
        
        # Token Expired logic
        if resp.status_code == 401 and tokens['refresh_token']:
            # Attempt refresh... (Implementation similar to previous steps)
            pass 
            
        return resp.text

@mcp.tool()
async def get_my_salary(session_name: str) -> str:
    """Get salary info. Requires the session_name used during auth."""
    return await hrms_api_call(session_name, "GET", "/api/payroll/user-salary-info/")

# --- START ---

def main():
    asyncio.run(init_db())
    port = int(os.getenv("PORT", 8000))
    mcp.run(transport="http", host="0.0.0.0", port=port)

if __name__ == "__main__":
    main()
