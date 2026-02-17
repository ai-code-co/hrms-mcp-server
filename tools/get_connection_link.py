import os 
async def get_connection_link() -> str:
    """Provides a link to securely link your account with this assistant."""
    SERVER_URL = os.getenv("SERVER_URL", "https://hrms-mcp-server.onrender.com") 
    return f"To access your HRMS data, visit this link and log in: {SERVER_URL}/connect\nAfter you get your 6-digit 'Sync Code', tell it to me."
