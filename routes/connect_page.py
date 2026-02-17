from fastapi.responses import HTMLResponse
from fastapi import Request

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