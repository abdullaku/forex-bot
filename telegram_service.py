from io import BytesIO
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

    async def send_photo(self, photo_bytes: bytes, caption: str) -> None:
        bio = BytesIO(photo_bytes)
        bio.name = "news.jpg"

        await self.bot.send_photo(
            chat_id=self.channel_id,
            photo=bio,
            caption=caption[:1024],
            parse_mode="HTML",
        )

    @staticmethod
    async def _download_image_bytes(url: str) -> bytes | None:
        """
        وێنەکە تەنها لە RAM دەخوێنێتەوە
        لەسەر دیسک هەڵی ناگرێت
        """
        if not url:
            return None

        timeout = aiohttp.ClientTimeout(total=10)
        max_size = 8 * 1024 * 1024  # 8MB

        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url, allow_redirects=True) as resp:
                    if resp.status != 200:
                        return None

                    content_type = resp.headers.get("Content-Type", "").lower()
                    if "image" not in content_type:
                        return None

                    content_length = resp.headers.get("Content-Length")
                    if content_length:
                        try:
                            if int(content_length) > max_size:
                                logger.warning("Image too large for Telegram fallback upload")
                                return None
                        except ValueError:
                            pass

                    data = bytearray()
                    async for chunk in resp.content.iter_chunked(64 * 1024):
                        data.extend(chunk)
                        if len(data) > max_size:
                            logger.warning("Image exceeded max size while downloading")
                            return None

                    return bytes(data) if data else None

        except Exception as e:
            logger.warning(f"Image download failed: {e}")
            return None

    async def send_news(self, text: str, image_url: str = None) -> None:
        if image_url:
            try:
                photo_bytes = await self._download_image_bytes(image_url)
                if photo_bytes:
                    await self.send_photo(photo_bytes, text)
                    return
            except Exception as e:
                logger.warning(f"Photo failed, sending text only: {e}")

        await self.send_message(text)
