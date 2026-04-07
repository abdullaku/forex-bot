import os
import re
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

        self.forbidden_script_pattern = re.compile(
            r"[\u0400-\u04FF"
            r"\u3040-\u30FF"
            r"\u0900-\u097F"
            r"\u0E00-\u0E7F"
            r"\u4E00-\u9FFF]"
        )

        self.allowed_inline_pattern = re.compile(
            r"[^0-9A-Za-z\u0600-\u06FF\s\.\,\:\%\$\€\£\(\)\-\/\'\"\؛\،\؟\!\+\•]"
        )

    def _create_filter_prompt(self, title: str, description: str = "") -> str:
        content = f"{title}\n{description}".strip()
        return (
            "You are a senior financial news editor for a Kurdish trading channel.\n\n"
            "Read the news below carefully and decide if it is directly relevant to Forex, commodities, macro, bonds, rates, stocks, oil, gold, crypto, or global markets.\n\n"
            "If NOT relevant → reply only: SKIP\n"
            "If relevant → reply only: YES\n\n"
            f"News:\n{content}"
        )

    def _create_translate_prompt(self, title: str, description: str = "") -> str:
        content = f"{title}\n{description}".strip()

        return (
            "You are a professional Kurdish financial news writer for a Telegram channel.\n\n"

            "Your task:\n"
            "Rewrite the news into NATURAL Central Kurdish (Sorani, Arabic script) in a clean modern Telegram format.\n\n"

            "Important writing rules:\n"
            "- Do NOT translate literally.\n"
            "- Understand the news first, then rewrite it professionally.\n"
            "- Keep the core facts exact.\n"
            "- Keep all important numbers, percentages, and financial facts accurate.\n"
            "- Do NOT invent facts.\n"
            "- Do NOT use dramatic clickbait.\n"
            "- Do NOT output explanations outside the final post.\n"
            "- Do NOT use markdown like ** or ##.\n"
            "- Write only in Sorani, but keep financial terms like Fed, USD, CPI, GDP, bond, yield naturally in English when needed.\n\n"

            "Dynamic style rules:\n"
            "- Start the first line with ONE suitable emoji based on the topic.\n"
            "- Examples: 💱 forex, 📈 rise, 📉 fall, 🪙 gold, 🛢 oil, ₿ crypto, 🏦 bonds/rates, 🌍 macro/geopolitics.\n"
            "- Do NOT always use the same emoji. Choose based on the news topic.\n"
            "- The impact section must be written intelligently based on this specific news, not as a repeated fixed sentence.\n"
            "- The wording must vary naturally depending on the article.\n\n"

            "Output format exactly:\n"
            "Line 1: [emoji] short strong headline in Kurdish\n"
            "Line 2: blank line\n"
            "Line 3: short summary paragraph, 1 to 2 sentences\n"
            "Line 4: blank line\n"
            "Line 5: 🧠 کاریگەری:\n"
            "Line 6: one smart market impact sentence or two short sentences based on the actual news\n\n"

            "Quality rules:\n"
            "- Headline should be short and sharp, not generic.\n"
            "- Summary should be concise and readable.\n"
            "- Impact should explain why the news matters for markets, traders, prices, sentiment, flows, yields, oil, gold, dollar, or risk appetite.\n"
            "- Different kinds of news must produce different impact wording.\n\n"

            "Return only the final formatted Kurdish post body.\n\n"

            f"News:\n{content}"
        )

    def _clean_line(self, line: str) -> str:
        line = self.forbidden_script_pattern.sub(" ", line)
        line = self.allowed_inline_pattern.sub(" ", line)
        line = re.sub(r"[ \t]+", " ", line).strip()
        return line

    def _clean_result(self, text: str) -> str:
        if not text:
            return ""

        text = text.replace("\r\n", "\n").replace("\r", "\n")
        raw_lines = text.split("\n")

        cleaned_lines = []
        blank_pending = False

        for raw in raw_lines:
            line = self._clean_line(raw)

            if not line:
                if cleaned_lines:
                    blank_pending = True
                continue

            if blank_pending and cleaned_lines:
                cleaned_lines.append("")
                blank_pending = False

            cleaned_lines.append(line)

        return "\n".join(cleaned_lines).strip()

    def _chat_sync(self, prompt: str) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            temperature=0.45,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content.strip()

    async def _chat(self, prompt: str) -> str:
        return await asyncio.to_thread(self._chat_sync, prompt)

    async def process(self, title: str, description: str = ""):
        try:
            filter_prompt = self._create_filter_prompt(title, description)
            filter_result = await self._chat(filter_prompt)

            if "SKIP" in filter_result.upper():
                logger.info(f"⏭️ Skipped: {title[:60]}")
                return None

            await asyncio.sleep(1)

            translate_prompt = self._create_translate_prompt(title, description)
            translated = await self._chat(translate_prompt)

            cleaned = self._clean_result(translated)

            if not cleaned or len(cleaned) < 20:
                return None

            logger.info(f"✅ Translated: {title[:60]}")
            return cleaned

        except Exception as e:
            logger.error(f"Translator error: {e}")
            return None


_translator = SmartTranslator()


async def process_smart_news(title: str, description: str = ""):
    return await _translator.process(title, description)
