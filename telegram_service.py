from telegram import Bot as TelegramBot
import logging
import aiohttp

logger = logging.getLogger(__name__)


class TelegramService:
    def __init__(self, token: str, channel_id: int):
        self.bot = TelegramBot(token=token)
        self.channel_id = channel_id

    async def send_message(self, text: str) -> None:
        await self.bot.send_message(
            chat_id=self.channel_id,
            text=text,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )

    async def send_photo(self, photo_url: str, caption: str) -> None:
        await self.bot.send_photo(
            chat_id=self.channel_id,
            photo=photo_url,
            caption=caption[:1024],
            parse_mode="HTML",
        )

    @staticmethod
    async def _is_valid_image(url: str) -> bool:
        """✅ content-type پشکنێت — نەک تەنها extension"""
        if not url:
            return False
        try:
            async with aiohttp.ClientSession() as session:
                async with session.head(
                    url,
                    timeout=aiohttp.ClientTimeout(total=5),
                    allow_redirects=True,
                ) as resp:
                    content_type = resp.headers.get("Content-Type", "")
                    return resp.status == 200 and "image" in content_type
        except Exception:
            return False

    async def send_news(self, text: str, image_url: str = None) -> None:
        if image_url and await self._is_valid_image(image_url):
            try:
                await self.send_photo(image_url, text)
                return
            except Exception as e:
                logger.warning(f"Photo failed, sending text only: {e}")

        await self.send_message(text)
