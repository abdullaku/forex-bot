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
    """
    AI is used only for clean Kurdish rewriting and summarizing.
    It does NOT decide whether to skip the news.
    Filtering must happen only at the source level in news.py.

    Final style:
      - Kurdish headline
      - Short Kurdish summary
      - No Forex importance section
      - No warning/disclaimer section
      - Source/link/time are added later by formatter.py
    """

    def __init__(self):
        self.client = Groq(api_key=TranslatorConfig.API_KEY)
        self.model = TranslatorConfig.MODEL

        self.forbidden_script_pattern = re.compile(
            r"[\u0400-\u04FF"
            r"\u3040-\u30FF"
            r"\u0900-\u097F"
            r"\u0E00-\u9FFF]"
        )

        self.allowed_inline_pattern = re.compile(
            r"[^0-9A-Za-z\u0600-\u06FF\s\.\,\:\%\$\€\£\(\)\-\/\'\"\؛\،\؟\!\+\•]"
        )

        self.blocked_section_markers = (
            "📰 هەواڵ:",
            "هەواڵ:",
            "📌 گرنگی بۆ Forex:",
            "گرنگی بۆ Forex:",
            "گرنگی بۆ فۆرێکس:",
            "⚠️ تێبینی:",
            "تێبینی:",
        )

    def _create_translate_prompt(
        self,
        title: str,
        description: str = "",
        source: str = "",
        currency: str = "",
    ) -> str:
        content = f"{title}\n{description}".strip()

        return (
            "You are a professional Kurdish editor for an official macroeconomic news Telegram channel.\n\n"

            "Important rule:\n"
            "- Do NOT decide whether this news should be skipped.\n"
            "- The source has already been approved as an official macro source.\n"
            "- Your job is only to rewrite the official news in clear Sorani Kurdish.\n\n"

            "Source context:\n"
            f"- Source: {source or 'Official source'}\n"
            f"- Currency: {currency or 'Unknown'}\n\n"

            "Writing rules:\n"
            "- Write in natural Central Kurdish Sorani using Arabic script.\n"
            "- Keep official names like Fed, BLS, BEA, ECB, Eurostat, BoE, ONS, BoJ, USD, EUR, GBP, JPY, CPI, GDP, PCE, NFP in English when useful.\n"
            "- Keep all numbers, dates, percentages, institution names, and official facts accurate.\n"
            "- Do NOT invent actual, forecast, previous, market reaction, or extra facts if not provided.\n"
            "- Do NOT explain Forex impact.\n"
            "- Do NOT mention Forex unless the original official title itself directly mentions foreign exchange.\n"
            "- Do NOT create trading signals.\n"
            "- Do NOT say BUY or SELL.\n"
            "- Do NOT use clickbait.\n"
            "- Do NOT output a warning, disclaimer, note, or advice.\n"
            "- Do NOT use section labels such as '📰 هەواڵ:', '📌 گرنگی بۆ Forex:', or '⚠️ تێبینی:'.\n"
            "- Do NOT output markdown like ** or ##.\n"
            "- Source, link, and time will be added by the system later, so do not include them.\n\n"

            "Output format exactly:\n"
            "Line 1: short clear Kurdish headline only, without emoji if not necessary\n"
            "Line 2: blank line\n"
            "Lines 3-5: short Kurdish summary in 2 to 3 sentences only\n\n"

            "Headline rules:\n"
            "- The headline must be clear and direct.\n"
            "- The headline should mention the main event, institution, or number when useful.\n"
            "- The headline should be one line only.\n\n"

            "Summary rules:\n"
            "- The summary must explain only what happened.\n"
            "- Use 2 to 3 concise sentences.\n"
            "- Mention the official source or institution when relevant.\n"
            "- Preserve important numbers and names from the official text.\n"
            "- Keep the full post body under 90 Kurdish words when possible.\n\n"

            "Return only the final Kurdish headline and summary.\n\n"

            f"Official news:\n{content}"
        )

    def _clean_line(self, line: str) -> str:
        line = self.forbidden_script_pattern.sub(" ", line)
        line = self.allowed_inline_pattern.sub(" ", line)
        line = re.sub(r"[ \t]+", " ", line).strip()
        return line

    def _remove_unwanted_sections(self, text: str) -> str:
        """Hard guard in case the model ignores the prompt."""
        if not text:
            return ""

        lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        kept = []
        skip_mode = False

        for raw in lines:
            line = raw.strip()

            if any(marker in line for marker in self.blocked_section_markers):
                if "گرنگی" in line or "Forex" in line or "فۆرێکس" in line or "تێبینی" in line:
                    skip_mode = True
                continue

            if skip_mode:
                continue

            lower_line = line.lower()
            if "signal" in lower_line or "سیگناڵ" in line or "buy" in lower_line or "sell" in lower_line:
                continue

            kept.append(raw)

        return "\n".join(kept).strip()

    def _clean_result(self, text: str) -> str:
        if not text:
            return ""

        text = self._remove_unwanted_sections(text)
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

        compact = []
        for line in cleaned_lines:
            if line == "" and compact and compact[-1] == "":
                continue
            compact.append(line)

        # Keep the post compact: headline + one blank + up to three summary lines.
        if len([x for x in compact if x]) > 4:
            non_empty = [x for x in compact if x]
            compact = [non_empty[0], ""] + non_empty[1:4]

        return "\n".join(compact).strip()

    def _chat_sync(self, prompt: str) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            temperature=0.25,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content.strip()

    async def _chat(self, prompt: str) -> str:
        return await asyncio.to_thread(self._chat_sync, prompt)

    async def process(
        self,
        title: str,
        description: str = "",
        source: str = "",
        currency: str = "",
    ):
        try:
            translate_prompt = self._create_translate_prompt(
                title=title,
                description=description,
                source=source,
                currency=currency,
            )

            translated = await self._chat(translate_prompt)
            cleaned = self._clean_result(translated)

            if not cleaned or len(cleaned) < 20:
                logger.warning(f"⚠️ Empty AI formatting result: {title[:60]}")
                return None

            logger.info(f"✅ Formatted official news: {title[:60]}")
            return cleaned

        except Exception as e:
            logger.error(f"Translator error: {e}")
            return None


_translator = SmartTranslator()


async def process_smart_news(
    title: str,
    description: str = "",
    source: str = "",
    currency: str = "",
):
    return await _translator.process(
        title=title,
        description=description,
        source=source,
        currency=currency,
    )
