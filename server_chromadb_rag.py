from fastmcp import FastMCP
import chromadb
from chromadb.api.models.Collection import Collection
from langchain_community.vectorstores import Chroma


CHROMA_API_KEY='ck-EjaCYQBCwJRbW4Wh1eGJRzDfZAiqAw73BbYUbFYAS5Ux'
CHROMA_TENANT='1cedb133-10a5-4fa3-bbfa-ff913e057895'
CHROME_DATABASE='TEST_RAG'
CHROMA_COLLECTION = "uipath_sec_doc"

mcp = FastMCP(name="My First MCP Server")

def createChromaClient():
    return  chromadb.CloudClient(
                    api_key=CHROMA_API_KEY,
                    tenant=CHROMA_TENANT,
                    database=CHROME_DATABASE
                )

chromaClient = createChromaClient()

@mcp.tool
def add(a: int, b: int) -> int:
    """Adds two integer numbers together."""
    return a + b

@mcp.resource("resource://config")
def get_config() -> dict:
    """Provides the application's configuration."""
    return {"version": "1.0", "author": "MyTeam"}

@mcp.resource("greetings://{name}")
def personalized_greeting(name: str) -> str:
    """Generates a personalized greeting for the given name."""
    return f"Hello, {name}! Welcome to the MCP server."



@mcp.tool()
def retrieve_uipath_security_doc(query:str) ->list[str]:
    """
     Used to search the UiPath security documents related to GenAI
        Returns:
            List of found documents
        """
    vectorstore = Chroma(
        client=chromaClient,
        collection_name=CHROMA_COLLECTION
    )

    retriever = vectorstore.as_retriever(
        search_type="similarity",
        search_kwargs={"k": 20}
    )
    docs = retriever.invoke(query)
    r=[]
    for doc in docs:
       r.append(doc.page_content)
    return r


if __name__ == "__main__":
    #mcp = FastMCP(name="My First MCP Server")
    mcp.run(transport="http", host="127.0.0.1", port=8000)