import asyncio
from fastmcp import Client, FastMCP
FAST_MCP_API_KEY = "fmcp_0bVoH4J5HmH7JF_TxZMluZVpImRZOhM3o7oEuUS9d3c"
client = Client("https://unfortunate-ivory-raven.fastmcp.app/mcp")
#client = Client("http://127.0.0.1:8000/mcp")
async def main():
    async with client:
        # Ensure client can connect
        await client.ping()

        # List available operations
        tools = await client.list_tools()
        resources = await client.list_resources()
        prompts = await client.list_prompts()

        #print(resources)
        #print(tools)
        # Ex. execute a tool call
        result = await client.call_tool("get_search",
                                        {"code_postal":"78000"
                                            #,"categorie_entreprise":"PME","est_ess":True
                                            #,"est_organisme_formation":True
                                         ,"prenoms_personne":"ahmed"
                                         ,"nom_personne":"gater"
                                         })
        #print(result.data)
        l = tools[0].model_dump_json()
        print(l)
asyncio.run(main())