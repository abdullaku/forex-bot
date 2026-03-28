import asyncio
import logging

from ئەپ import ForexBotApp

logging.basicConfig(level=logging.INFO)


async def main():
    app = ForexBotApp()
    await app.run()


if __name__ == "__main__":
    asyncio.run(main())
