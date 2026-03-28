from telegram import Bot as TelegramBot


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

    async def send_news(self, text: str, image_url: str = None) -> None:
        if image_url:
            await self.send_photo(image_url, text)
        else:
            await self.send_message(text)
