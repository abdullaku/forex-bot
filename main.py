import asyncio
import logging
import re

from app import ForexBotApp


# ─────────────────────────────────────────────────────────────
# 🔐 Mask secrets (Telegram token)
# ─────────────────────────────────────────────────────────────
def _mask_secrets(value):
    if not isinstance(value, str):
        try:
            value = str(value)
        except Exception:
            return value

    masked = value

    # Telegram bot token (plain or inside URL)
    masked = re.sub(
        r'bot\d+:[A-Za-z0-9_-]+',
        'bot[TELEGRAM_TOKEN_REDACTED]',
        masked,
    )

    masked = re.sub(
        r'(https://api\.telegram\.org/)bot\d+:[A-Za-z0-9_-]+',
        r'\1bot[TELEGRAM_TOKEN_REDACTED]',
        masked,
    )

    return masked


class SecretFilter(logging.Filter):
    def filter(self, record):
        try:
            # 🔥 render full message first (important fix)
            msg = record.getMessage()
            msg = _mask_secrets(msg)

            record.msg = msg
            record.args = ()

        except Exception:
            pass

        return True


def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s:%(name)s:%(message)s",
    )

    secret_filter = SecretFilter()

    # Root logger
    root_logger = logging.getLogger()
    for handler in root_logger.handlers:
        handler.addFilter(secret_filter)

    # 🔥 reduce sensitive logging from libraries
    for logger_name in ("httpx", "httpcore", "telegram", "telegram.ext"):
        lib_logger = logging.getLogger(logger_name)
        lib_logger.setLevel(logging.WARNING)  # was INFO
        lib_logger.propagate = True

        for handler in lib_logger.handlers:
            handler.addFilter(secret_filter)

    # 🔐 extra safety at record creation
    old_factory = logging.getLogRecordFactory()

    def record_factory(*args, **kwargs):
        record = old_factory(*args, **kwargs)
        try:
            msg = record.getMessage()
            msg = _mask_secrets(msg)

            record.msg = msg
            record.args = ()
        except Exception:
            pass
        return record

    logging.setLogRecordFactory(record_factory)


# ─────────────────────────────────────────────────────────────
# 🚀 Main
# ─────────────────────────────────────────────────────────────
async def main():
    setup_logging()
    app = ForexBotApp()
    await app.run()


if __name__ == "__main__":
    asyncio.run(main())
