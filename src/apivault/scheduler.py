"""APScheduler-based task scheduler for API discovery and enrichment jobs."""

import asyncio


async def main():
    """Run the scheduler process."""
    # TODO: Initialize APScheduler with discovery, validation, and enrichment jobs
    while True:
        await asyncio.sleep(60)


if __name__ == "__main__":
    asyncio.run(main())
