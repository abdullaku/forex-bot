import asyncio
import logging
import re

from app import ForexBotApp


TOKEN_PATTERNS = [
    re.compile(r'bot\d+:[A-Za-z0-9_-]+'),
    re.compile(r'(https://api\.telegram\.org/)bot\d+:[A-Za-z0-9_-]+'),
]


def _mask_secrets(value):
    if not isinstance(value, str):
        return value

    masked = value

    # Telegram bot token in plain form
    masked = re.sub(
        r'bot\d+:[A-Za-z0-9_-]+',
        'bot[TELEGRAM_TOKEN_REDACTED]',
        masked,
    )

    # Safety for full Telegram API URLs
    masked = re.sub(
        r'(https://api\.telegram\.org/)bot\d+:[A-Za-z0-9_-]+',
        r'\1bot[TELEGRAM_TOKEN_REDACTED]',
        masked,
    )

    return masked


class SecretFilter(logging.Filter):
    def filter(self, record):
        try:
            record.msg = _mask_secrets(record.msg)

            if record.args:
                if isinstance(record.args, dict):
                    record.args = {
                        k: _mask_secrets(v) if isinstance(v, str) else v
                        for k, v in record.args.items()
                    }
                elif isinstance(record.args, tuple):
                    record.args = tuple(
                        _mask_secrets(v) if isinstance(v, str) else v
                        for v in record.args
                    )
                else:
                    if isinstance(record.args, str):
                        record.args = _mask_secrets(record.args)
        except Exception:
            pass

        return True


def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s:%(name)s:%(message)s",
    )

    secret_filter = SecretFilter()

    # Root handlers
    root_logger = logging.getLogger()
    for handler in root_logger.handlers:
        handler.addFilter(secret_filter)

    # Common noisy libraries that may log raw URLs
    for logger_name in ("httpx", "httpcore", "telegram", "telegram.ext"):
        lib_logger = logging.getLogger(logger_name)
        lib_logger.setLevel(logging.INFO)
        lib_logger.propagate = True

        for handler in lib_logger.handlers:
            handler.addFilter(secret_filter)

    # Extra safety: mask at LogRecord creation time
    old_factory = logging.getLogRecordFactory()

    def record_factory(*args, **kwargs):
        record = old_factory(*args, **kwargs)
        try:
            record.msg = _mask_secrets(record.msg)

            if record.args:
                if isinstance(record.args, dict):
                    record.args = {
                        k: _mask_secrets(v) if isinstance(v, str) else v
                        for k, v in record.args.items()
                    }
                elif isinstance(record.args, tuple):
                    record.args = tuple(
                        _mask_secrets(v) if isinstance(v, str) else v
                        for v in record.args
                    )
                else:
                    if isinstance(record.args, str):
                        record.args = _mask_secrets(record.args)
        except Exception:
            pass

        return record

    logging.setLogRecordFactory(record_factory)


async def main():
    setup_logging()
    app = ForexBotApp()
    await app.run()


if __name__ == "__main__":
    asyncio.run(main())
