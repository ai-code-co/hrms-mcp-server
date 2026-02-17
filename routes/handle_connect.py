import httpx
from fastapi.responses import HTMLResponse
from fastapi import Request
import os 
import secrets

from database import get_db_connection


async def handle_connect(request: Request):
    form = await request.form()
    username, password = form.get("username"), form.get("password")
    if not username or not password:
        return HTMLResponse(
            "<h1>Login Failed</h1><p>Missing username or password.</p><a href='/connect'>Try again</a>",
            status_code=400
        )
    
    async with httpx.AsyncClient() as client:
        base_url = os.getenv("HRMS_API_BASE_URL", "https://hrms-backend-1-m8ml.onrender.com").rstrip("/")
        login_url = f"{base_url}/api/auth/login/"
        r = await client.post(login_url, json={"username": username, "password": password})
        print("LOGIN URL:", login_url)
        print("LOGIN STATUS:", r.status_code)
        print("LOGIN BODY:", r.text)

        if r.status_code == 200:
            data = r.json()
            pairing_code = "".join(secrets.choice("0123456789") for _ in range(6))
            conn = await get_db_connection()
            await conn.execute("INSERT INTO pairing_codes (code, access_token, refresh_token) VALUES ($1, $2, $3)",
                             pairing_code, data.get("access"), data.get("refresh"))
            await conn.close()
            return HTMLResponse(f"<h1>Connected!</h1><p>Sync Code: <b style='font-size: 24px;'>{pairing_code}</b></p><p>Give this code to the chat assistant.</p>")
        if r.status_code == 401:
            return HTMLResponse("<h1>Error</h1><p>Invalid credentials.</p>", status_code=401)
        if r.status_code == 429:
            retry_after = r.headers.get("Retry-After", "60")
            return HTMLResponse(
                f"<h1>Rate Limited</h1><p>Too many login attempts. Try again after {retry_after} seconds.</p>",
                status_code=429
            )
        return HTMLResponse(f"<h1>Error</h1><p>Login failed ({r.status_code}).</p>", status_code=502)
