import asyncio
from fastmcp import Client, FastMCP
FAST_MCP_API_KEY = "fmcp_0bVoH4J5HmH7JF_TxZMluZVpImRZOhM3o7oEuUS9d3c"
#client = Client("https://unfortunate-ivory-raven.fastmcp.app/mcp")
client = Client("http://127.0.0.1:8000/mcp")
async def main():
    async with client:
        # Ensure client can connect
        await client.ping()

        # List available operations
        tools = await client.list_tools()
        resources = await client.list_resources()
        prompts = await client.list_prompts()

        #print(resources)
        print(tools)
        # Ex. execute a tool call
        result = await client.call_tool("get_search", {"q": "SFR"})
        print(result)

asyncio.run(main())