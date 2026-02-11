import os
import sys
import random
import httpx
from fastmcp import FastMCP
import asyncpg
from dotenv import load_dotenv
import asyncio


# Load variables from .env file
load_dotenv()

# BASE_URL = "https://hrms-backend-1-m8ml.onrender.com"

mcp = FastMCP(name="Demo Server")

# Configuration from Environment Variables
BASE_URL = os.getenv("HRMS_API_BASE_URL", "https://hrms-backend-1-m8ml.onrender.com")
# CLIENT_ID = os.getenv("HRMS_CLIENT_ID")
# CLIENT_SECRET = os.getenv("HRMS_CLIENT_SECRET")
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is missing (set it in Render Environment Variables).")


# --- DATABASE HELPER ---

async def get_db_connection():
    return await asyncpg.connect(DATABASE_URL)

async def init_db():
    """Ensure the tokens table exists."""
    conn = await get_db_connection()
    try:
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS hrms_tokens (
                client_id TEXT PRIMARY KEY,
                access_token TEXT,
                refresh_token TEXT
            )
        ''')
    finally:
        await conn.close()
        
        
def get_hrms_credentials():
    ctx = mcp.ctx
    if not ctx or not ctx.request:
        raise RuntimeError("No request context available")

    headers = ctx.request.headers

    client_id = headers.get("x-hrms-client-id")
    client_secret = headers.get("x-hrms-client-secret")

    if not client_id or not client_secret:
        raise RuntimeError("Missing HRMS credentials in headers")

    return (
        client_id,
        client_secret
    )    
        
# --- AUTH LOGIC HELPERS ---

async def save_tokens(access: str, refresh: str):
    client_id,_ = get_hrms_credentials()
    conn = await get_db_connection()
    try:
        await conn.execute('''
            INSERT INTO hrms_tokens (client_id, access_token, refresh_token)
            VALUES ($1, $2, $3)
            ON CONFLICT (client_id) DO UPDATE 
            SET access_token = EXCLUDED.access_token, 
                refresh_token = EXCLUDED.refresh_token
        ''', client_id, access, refresh)
    finally:
        await conn.close()

async def get_stored_tokens():
    conn = await get_db_connection()
    client_id,_ = get_hrms_credentials()
    try:
        row = await conn.fetchrow('SELECT access_token, refresh_token FROM hrms_tokens WHERE client_id = $1', client_id)
        return row if row else None
    finally:
        await conn.close()

async def perform_fresh_login():
    """Internal helper to login and store tokens."""
    url = f"{BASE_URL}/auth/login/"
    client_id,client_secret = get_hrms_credentials()
    payload = {"username": client_id, "password": client_secret}
    
    async with httpx.AsyncClient() as client:
        r = await client.post(url, json=payload)
        if r.status_code == 200:
            data = r.json()
            access = data.get("access") or data.get("token")
            refresh = data.get("refresh")
            await save_tokens(access, refresh)
            return access
        else:
            raise Exception(f"Login failed: {r.text}")

async def refresh_access_token(refresh_token: str):
    """Attempt to get a new access token using the refresh token."""
    url = f"{BASE_URL}/api/auth/refresh-token/" 
    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(url, json={"refresh": refresh_token})
            if r.status_code == 200:
                data = r.json()
                new_access = data.get("access")
                new_refresh = data.get("refresh", refresh_token)
                await save_tokens(new_access, new_refresh)
                return new_access
    except:
        return None
    return None

async def get_authenticated_client():
    """
    Returns an httpx client with the valid Bearer token.
    Handles the expired -> refresh -> login logic.
    """
    tokens = await get_stored_tokens()
    
    if not tokens:
        access_token = await perform_fresh_login()
    else:
        access_token = tokens['access_token']

    return access_token

        
# --- NEW TOOLS ---
async def hrms_request(method: str, endpoint: str, params: dict = None, json_body: dict = None):
    """
    Flexible wrapper for GET and POST.
    - params: used for query strings (?page=1&search=...)
    - json_body: used for POST/PUT request bodies
    """
    access_token = await get_authenticated_client()
    url = f"{BASE_URL}{endpoint}"
    
    async with httpx.AsyncClient(timeout=15.0) as client:
        def get_headers(token): return {"Authorization": f"Bearer {token}"}
        
        # Initial request
        response = await client.request(
            method, url, 
            headers=get_headers(access_token), 
            params=params, 
            json=json_body
        )
        
        # Handle 401 (Expired)
        if response.status_code == 401:
            tokens = await get_stored_tokens()
            new_token = None
            
            if tokens and tokens['refresh_token']:
                new_token = await refresh_access_token(tokens['refresh_token'])
            
            if not new_token:
                new_token = await perform_fresh_login()
                
            # Retry request with new token
            response = await client.request(
                method, url, 
                headers=get_headers(new_token), 
                params=params, 
                json=json_body
            )

        return response

@mcp.tool()
async def get_my_salary() -> str:
    """User Tool: Get current user's salary information."""
    try:
        # Assuming endpoint is /employees/me/salary/
        resp = await hrms_request("GET", "/employees/me/salary-info/")
        if resp.status_code == 200:
            return f"Salary Info: {resp.text}"
        return f"Error fetching salary: {resp.status_code} {resp.text}"
    except Exception as e:
        return f"Error: {str(e)}"

@mcp.tool()
async def list_employees() -> str:
    """Admin Tool: Get list of all active employees."""
    try:
        
        resp = await hrms_request("GET", "/api/employees/")
        if resp.status_code == 200:
            return f"Employee List: {resp.text}"
        return f"Error listing employees: {resp.status_code} {resp.text}"
    except Exception as e:
        return f"Error: {str(e)}"     
    
@mcp.tool()
async def list_attendance(
    employee_id: str = None,
    date: str = None,
    page: int = 1
) -> str:
    """
    Admin Tool: Get attendance records for all employees.
    :param employee_id: Optional filter by specific employee ID.
    :param date: Optional filter by date (format YYYY-MM-DD).
    :param page: Page number for pagination.
    """
    try:
        params = {"page": page}
        if employee_id: params["employee_id"] = employee_id
        if date: params["date"] = date

        resp = await hrms_request("GET", "/api/attendance/", params=params)
        
        if resp.status_code == 200:
            return f"Attendance Records (Page {page}):\n{resp.text}"
        return f"Error {resp.status_code}: {resp.text}"
    except Exception as e:
        return f"Error fetching attendance: {str(e)}"  
    
@mcp.tool()
async def list_departments(
    search: str = None,
    page: int = 1
) -> str:
    """
    Get a list of all company departments.
    :param search: Optional search term to filter departments by name.
    :param page: Page number for pagination.
    """
    try:
        params = {"page": page}
        if search: params["search"] = search

        resp = await hrms_request("GET", "/api/departments/", params=params)
        
        if resp.status_code == 200:
            return f"Departments List:\n{resp.text}"
        return f"Error {resp.status_code}: {resp.text}"
    except Exception as e:
        return f"Error fetching departments: {str(e)}"

@mcp.tool()
async def list_holidays(
    year: int = None,
    page: int = 1
) -> str:
    """
    Get the list of company holidays.
    :param year: Optional filter to see holidays for a specific year.
    :param page: Page number for pagination.
    """
    try:
        params = {"page": page}
        if year: params["year"] = year

        resp = await hrms_request("GET", "/api/holidays/", params=params)
        
        if resp.status_code == 200:
            return f"Holiday Calendar:\n{resp.text}"
        return f"Error {resp.status_code}: {resp.text}"
    except Exception as e:
        return f"Error fetching holidays: {str(e)}"         

@mcp.tool()
def roll_dice(n_dice: int = 1) -> list[int]:
    return [random.randint(1, 6) for _ in range(n_dice)]

@mcp.tool()
def add_numbers(a: float, b: float) -> float:
    return a + b




def main():
    
    
    try:
        asyncio.run(init_db())
    except Exception as e:
        print(f"[WARN] init_db failed: {e}", file=sys.stderr)
    
    # print("[HRMS Server] starting...", file=sys.stderr)
    # mcp.run(transport="stdio")
    port = int(os.getenv("PORT", 8000))
    print(f"[HRMS Server] starting on port {port} using SSE...", file=sys.stderr)
    mcp.run(transport="sse", host="0.0.0.0", port=port)

if __name__ == "__main__":
    main()