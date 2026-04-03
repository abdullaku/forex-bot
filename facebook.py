import re
import logging
import aiohttp

from formatter import TextFormatter

logger = logging.getLogger(__name__)


class FacebookService:
    def __init__(self, page_id: str, page_token: str):
        self.page_id = page_id
        self.page_token = page_token

    async def post(self, text: str, image_url: str = None, link_url: str = None) -> None:
        try:
            clean = TextFormatter.clean_text(text)
            clean = re.sub(r"🔗.*", "", clean).strip()
            clean = re.sub(r"\n{3,}", "\n\n", clean).strip()

            if image_url:
                # وێنە هەیە — بە /photos بنێرە، لینکەکەش لە caption زیاد بکە
                if link_url:
                    clean = f"{clean}\n\n🔗 {link_url}"
                endpoint = f"https://graph.facebook.com/v19.0/{self.page_id}/photos"
                data = {
                    "url": image_url,
                    "caption": clean,
                    "access_token": self.page_token,
                }
            elif link_url:
                # وێنە نییە، تەنها لینک
                endpoint = f"https://graph.facebook.com/v19.0/{self.page_id}/feed"
                data = {
                    "message": clean,
                    "link": link_url,
                    "access_token": self.page_token,
                }
            else:
                # تەنها تێکست — دینار، نرخ، ئتد
                endpoint = f"https://graph.facebook.com/v19.0/{self.page_id}/feed"
                data = {
                    "message": clean,
                    "access_token": self.page_token,
                }

            async with aiohttp.ClientSession() as session:
                async with session.post(endpoint, data=data, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    if resp.status not in (200, 201):
                        text_resp = await resp.text()
                        logger.error(f"FB Error {resp.status}: {text_resp}")

        except Exception as e:
            logger.error(f"FB Error: {type(e).__name__}: {e}")
