import asyncio
import os

from dotenv import load_dotenv
from fastmcp import FastMCP

load_dotenv()

from database.schema_setup import init_db
from routes import register_routes
from tools import register_tools

mcp = FastMCP(name="HRMS Connector")
register_routes(mcp)
register_tools(mcp)


def main():
    asyncio.run(init_db())
    port = int(os.getenv("PORT", 8000))
    mcp.run(transport="sse", host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
