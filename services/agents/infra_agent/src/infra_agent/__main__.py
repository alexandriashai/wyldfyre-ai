"""Entry point for running infra_agent as a module."""

import asyncio
from .agent import main

if __name__ == "__main__":
    asyncio.run(main())
