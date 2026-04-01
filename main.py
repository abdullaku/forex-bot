import asyncio
import logging
import re

from app import ForexBotApp


class SecretFilter(logging.Filter):
    def filter(self, record):
        try:
            if isinstance(record.msg, str):
                record.msg = re.sub(
                    r'bot\d+:[A-Za-z0-9_-]+',
                    'bot[TELEGRAM_TOKEN_REDACTED]',
                    record.msg
                )
        except Exception:
            pass
        return True


logging.basicConfig(level=logging.INFO)

for handler in logging.getLogger().handlers:
    handler.addFilter(SecretFilter())


async def main():
    app = ForexBotApp()
    await app.run()


if __name__ == "__main__":
    asyncio.run(main())
