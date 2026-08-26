# Minimal Agent → MCP

```bash
pip install lime-agents-sdk
export LIME_AGENT_TOKEN=at_...
export MCP_SERVER_URL=https://your-mcp.example/mcp
python main.py
```

```python
# main.py
import asyncio
import os

from lime_agents import LimeAgent


async def main() -> None:
    url = os.environ["MCP_SERVER_URL"]
    async with LimeAgent() as agent:
        tools = await agent.list_tools(url)
        print([t.name for t in tools])


asyncio.run(main())
```
