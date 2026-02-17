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
SERVER_URL = os.getenv("SERVER_URL", "https://hrms-mcp-server.onrender.com") 

mcp = FastMCP(name="HRMS Connector")

# --- DATABASE ---

async def get_db_connection():
    return await asyncpg.connect(DATABASE_URL)

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

# --- WEB UI ---

@mcp.custom_route("/connect", methods=["GET"])
async def connect_page(request: Request):
    """Secure connection page."""
    return HTMLResponse("""
    <html>
        <body style="font-family: sans-serif; text-align: center; padding-top: 50px;">
            <h2>Link your HRMS Account</h2>
            <form action="/connect" method="post">
                <input type="text" name="username" placeholder="Username" style="padding:10px;" required><br><br>
                <input type="password" name="password" placeholder="Password" style="padding:10px;" required><br><br>
                <button type="submit" style="padding:10px 20px;">Get Sync Code</button>
            </form>
        </body>
    </html>
    """)

@mcp.custom_route("/connect", methods=["POST"])
async def handle_connect(request: Request):
    form = await request.form()
    username, password = form.get("username"), form.get("password")
    
    async with httpx.AsyncClient() as client:
        r = await client.post(f"{BASE_URL}/auth/login/", json={"username": username, "password": password})
        if r.status_code == 200:
            data = r.json()
            pairing_code = "".join(secrets.choice("0123456789") for _ in range(6))
            conn = await get_db_connection()
            await conn.execute("INSERT INTO pairing_codes (code, access_token, refresh_token) VALUES ($1, $2, $3)",
                             pairing_code, data.get("access"), data.get("refresh"))
            await conn.close()
            return HTMLResponse(f"<h1>Connected!</h1><p>Sync Code: <b style='font-size: 24px;'>{pairing_code}</b></p><p>Give this code to the chat assistant.</p>")
        return HTMLResponse("<h1>Error</h1><p>Invalid credentials.</p>", status_code=401)

# --- REFRESH LOGIC ---

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

# --- TOOLS (RE-WORDED FOR SAFETY) ---

@mcp.tool()
async def get_connection_link() -> str:
    """Provides a link to securely link your account with this assistant."""
    return f"To access your HRMS data, visit this link and log in: {SERVER_URL}/connect\nAfter you get your 6-digit 'Sync Code', tell it to me."

@mcp.tool()
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

async def hrms_api_call(endpoint: str, method="GET", params=None):
    conn = await get_db_connection()
    tokens = await conn.fetchrow("SELECT access_token, refresh_token FROM user_sessions WHERE session_id = 'default'")
    await conn.close()

    if not tokens:
        return "Not connected. Please use the 'get_connection_link' tool first."

    async with httpx.AsyncClient(timeout=20.0) as client:
        headers = {"Authorization": f"Bearer {tokens['access_token']}"}
        resp = await client.request(method, f"{BASE_URL}{endpoint}", headers=headers, params=params)
        
        if resp.status_code == 401: # Expired
            new_access = await refresh_tokens('default', tokens['refresh_token'])
            if new_access:
                headers["Authorization"] = f"Bearer {new_access}"
                resp = await client.request(method, f"{BASE_URL}{endpoint}", headers=headers, params=params)
        
        return resp.text

# ---MCP Tools---
@mcp.tool()
async def get_my_salary(session_name: str) -> str:
    """Get salary info. Requires the session_name used during auth."""
    return await hrms_api_call(session_name, "GET", "/api/payroll/user-salary-info/")

@mcp.tool()
async def get_user_salary_info(
    session_name: str,
    userid: int = None,
    month: int = None,
    year: int = None
) -> str:
    """
    Get salary info from user-salary-info endpoint.
    The backend enforces role-based visibility and access rules.
    :param userid: Optional employee ID.
    :param month: Optional month (1-12).
    :param year: Optional year (e.g., 2026).
    """
    if month is not None and (month < 1 or month > 12):
        return "Error: 'month' must be between 1 and 12."

    params = {}
    if userid is not None:
        params["userid"] = userid
    if month is not None:
        params["month"] = month
    if year is not None:
        params["year"] = year

    return await hrms_api_call(session_name, "GET", "/api/payroll/user-salary-info/", params=params or None)

@mcp.tool()
async def list_holidays(
    session_name: str,
    year: int = None,
    page: int = 1
) -> str:
    """
    Get the list of company holidays.
    :param year: Optional filter to see holidays for a specific year.
    :param page: Page number for pagination.
    """
    params = {"page": page}
    if year is not None:
        params["year"] = year
    return await hrms_api_call(session_name, "GET", "/api/holidays/", params=params)

@mcp.tool()
async def list_attendance(
    session_name: str,
    search: str = None,
    ordering: str = None,
    page: int = 1
) -> str:
    """
    Get attendance records.
    :param search: Optional search term.
    :param ordering: Optional ordering field.
    :param page: Page number for pagination.
    """
    params = {"page": page}
    if search:
        params["search"] = search
    if ordering:
        params["ordering"] = ordering
    return await hrms_api_call(session_name, "GET", "/api/attendance/", params=params)

@mcp.tool()
async def get_monthly_attendance(
    session_name: str,
    month: int,
    year: int,
    search: str = None,
    ordering: str = None,
    page: int = 1,
    userid: int = None
) -> str:
    """
    Get monthly attendance summary for an employee.
    :param month: Month number (1-12).
    :param year: Year (e.g., 2026).
    :param search: Optional search term.
    :param ordering: Optional ordering field.
    :param page: Page number for pagination.
    :param userid: Optional employee ID (admin only).
    """
    if month < 1 or month > 12:
        return "Error: 'month' must be between 1 and 12."

    params = {
        "month": month,
        "year": year,
        "page": page
    }
    if search:
        params["search"] = search
    if ordering:
        params["ordering"] = ordering
    if userid is not None:
        params["userid"] = userid

    return await hrms_api_call(session_name, "GET", "/api/attendance/monthly/", params=params)

@mcp.tool()
async def get_my_attendance_history(
    session_name: str,
    start_date: str = None,
    end_date: str = None,
    search: str = None,
    ordering: str = None,
    page: int = 1
) -> str:
    """
    Get logged-in employee attendance history.
    :param start_date: Optional start date (YYYY-MM-DD).
    :param end_date: Optional end date (YYYY-MM-DD).
    :param search: Optional search term.
    :param ordering: Optional ordering field.
    :param page: Page number for pagination.
    """
    params = {"page": page}
    if start_date:
        params["start_date"] = start_date
    if end_date:
        params["end_date"] = end_date
    if search:
        params["search"] = search
    if ordering:
        params["ordering"] = ordering

    return await hrms_api_call(session_name, "GET", "/api/attendance/my-attendance/", params=params)

@mcp.tool()
async def get_today_attendance(
    session_name: str,
    search: str = None,
    ordering: str = None,
    page: int = 1
) -> str:
    """
    Get today's attendance for the logged-in employee.
    :param search: Optional search term.
    :param ordering: Optional ordering field.
    :param page: Page number for pagination.
    """
    params = {"page": page}
    if search:
        params["search"] = search
    if ordering:
        params["ordering"] = ordering

    return await hrms_api_call(session_name, "GET", "/api/attendance/today/", params=params)

# --- START ---

def main():
    asyncio.run(init_db())
    port = int(os.getenv("PORT", 8000))
    mcp.run(transport="sse", host="0.0.0.0", port=port)

if __name__ == "__main__":
    main()
