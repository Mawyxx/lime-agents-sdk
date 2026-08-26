"""Headless site-login approve (PoW + X-Agent-Token)."""

from __future__ import annotations

import asyncio
import os

from lime_agents import ApiError, LimeAgent, PowTimeoutError


async def main() -> None:
    request_id = os.environ["LIME_LOGIN_REQUEST_ID"]
    # One LimeAgent per worker process in production — reuse across jobs.
    agent = LimeAgent(agent_token=os.environ["LIME_AGENT_TOKEN"])
    try:
        result = await agent.login(request_id)
        print(result.status, result.approved_agent_id)
    except PowTimeoutError:
        print("PoW timeout — increase pow_timeout or retry")
    except ApiError as exc:
        print(f"[{exc.code}] {exc.message}")
    finally:
        await agent.aclose()


if __name__ == "__main__":
    asyncio.run(main())
