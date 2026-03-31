import os
import asyncio
import logging
from groq import Groq

logger = logging.getLogger(__name__)


class TranslatorConfig:
    API_KEY = os.getenv("GROQ_API_KEY")
    MODEL = "llama-3.3-70b-versatile"

    @classmethod
    def validate(cls):
        if not cls.API_KEY:
            raise ValueError("❌ GROQ_API_KEY is not set in environment variables")


TranslatorConfig.validate()


class SmartTranslator:
    def __init__(self):
        self.client = Groq(api_key=TranslatorConfig.API_KEY)
        self.model = TranslatorConfig.MODEL

    def _create_prompt(self, title: str, description: str = "") -> str:
        content = f"{title}\n{description}".strip()

        return (
            "You are a Forex news editor for a Kurdish trading channel.\n\n"
            "Read this news carefully:\n"
            f"{content}\n\n"
            "STEP 1 — Decide if this news is DIRECTLY relevant to Forex traders:\n"
            "- RELEVANT: news about currency pairs (EUR/USD, GBP/USD, USD/JPY etc.), "
            "gold (XAU/USD), oil prices, central bank decisions (Fed, ECB, BOE, BOJ), "
            "inflation data, interest rates, NFP, CPI, GDP that directly moves Forex markets.\n"
            "- NOT RELEVANT: general stock market news, company earnings, crypto, "
            "sports, politics without direct Forex impact, general business news.\n\n"
            "STEP 2 — If NOT RELEVANT, reply with exactly: SKIP\n\n"
            "STEP 3 — If RELEVANT, translate and summarize into Kurdish Sorani:\n"
            "1. Write one strong Kurdish title.\n"
            "2. Write one short Kurdish summary (2-3 sentences max).\n"
            "3. Kurdish Sorani only. No English.\n"
            "4. No markdown. No ** or * or bullets or hashtags.\n"
            "5. Plain clean text only.\n"
            "6. Output format must be exactly:\n"
            "TITLE\n\nSUMMARY"
        )

    def _clean_result(self, text: str) -> str:
        text = text.replace("**", "")
        text = text.replace("__", "")
        text = text.replace("```", "")
        text = text.replace("##", "")
        text = text.replace("*", "")
        return text.strip()

    def _chat_sync(self, prompt: str) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content.strip()

    async def _chat(self, prompt: str) -> str:
        return await asyncio.to_thread(self._chat_sync, prompt)

    async def process(self, title: str, description: str = ""):
        try:
            prompt = self._create_prompt(title, description)
            result = await self._chat(prompt)

            # ئەگەر AI گوتی SKIP — هەواڵەکە پەیوەندی بە فۆرێکس نییە
            result_upper = result.strip().upper()
            if result_upper == "SKIP" or result_upper.startswith("SKIP"):
                logger.info(f"⏭️ Skipped (not Forex relevant): {title[:60]}")
                return None

            cleaned = self._clean_result(result)
            logger.info(f"✅ Translated: {title[:60]}")
            return cleaned

        except Exception as e:
            logger.error(f"Translator error: {e}")
            return None


_translator = SmartTranslator()


async def process_smart_news(title: str, description: str = ""):
    return await _translator.process(title, description)
