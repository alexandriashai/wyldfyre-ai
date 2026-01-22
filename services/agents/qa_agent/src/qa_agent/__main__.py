"""Entry point for running qa_agent as a module."""

import asyncio
from .agent import main

if __name__ == "__main__":
    asyncio.run(main())
