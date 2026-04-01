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
            r"[\u0400-\u04FF"   # Cyrillic
            r"\u3040-\u30FF"    # Hiragana + Katakana
            r"\u0900-\u097F"    # Devanagari
            r"\u0E00-\u0E7F"    # Thai
            r"\u4E00-\u9FFF]"   # CJK Unified Ideographs
        )

        self.allowed_punctuation_pattern = re.compile(r"[^0-9A-Za-z\u0600-\u06FF\s\.,:%$€£()\-\/'\":؛،؟!+]")

    def _create_prompt(self, title: str, description: str = "", strict: bool = False) -> str:
        content = f"{title}\n{description}".strip()

        strict_block = ""
        if strict:
            strict_block = (
                "\nIMPORTANT RETRY RULES:\n"
                "- Your previous answer contained mixed or foreign script.\n"
                "- This time output ONLY Sorani Kurdish in Arabic script.\n"
                "- Never output Cyrillic, Japanese, Hindi, Turkish, Kurmanji, or any foreign letters.\n"
                "- Keep only true English proper nouns exactly as they are.\n"
                "- If a word is not a proper noun, translate it into Sorani Kurdish.\n"
            )

        return (
            "You are a senior financial news editor for a Kurdish trading channel.\n\n"
            "Read the news below carefully and decide if it is directly relevant to Forex traders.\n\n"
            "Forex-relevant topics include:\n"
            "- Currency pairs like EUR/USD, GBP/USD, USD/JPY, USD/CAD\n"
            "- Gold, XAU/USD, oil, Brent, WTI\n"
            "- Central banks such as Fed, ECB, BOE, BOJ\n"
            "- Interest rates, inflation, CPI, PPI, NFP, GDP\n"
            "- Macro or geopolitical news ONLY if it directly affects currencies, gold, or oil\n\n"
            "Not relevant topics include:\n"
            "- General stock market chatter without Forex impact\n"
            "- Company earnings without Forex impact\n"
            "- Sports, crime, entertainment, lifestyle, general politics\n\n"
            "If the news is NOT directly relevant, reply with exactly: SKIP\n\n"
            "If the news IS relevant, follow these rules strictly:\n"
            "1. Write in Central Kurdish (Sorani) only.\n"
            "2. Never mix in Kurmanji or any foreign language.\n"
            "3. Never output Russian, Japanese, Hindi, Persian, Turkish, or any foreign script.\n"
            "4. Keep English proper nouns exactly as they are only when necessary, such as person names, company names, media names, country names, symbols, or brand names.\n"
            "5. Translate all common words into natural Sorani Kurdish.\n"
            "6. Use simple, fluent, news-style Sorani.\n"
            "7. Do not add markdown, bullets, hashtags, explanations, or quotation marks.\n"
            "8. Output format must be exactly:\n"
            "TITLE\n\nSUMMARY\n\n"
            "Examples:\n"
            '- "currency markets" -> "بازاڕەکانی دراو"\n'
            '- "tanker" -> "تانکەر"\n'
            '- "America" -> "ئەمریکا"\n'
            '- "Bloomberg" -> "Bloomberg"\n'
            '- "M. Rom" -> "M. Rom"\n'
            f"{strict_block}\n"
            "News:\n"
            f"{content}"
        )

    def _strip_markdown(self, text: str) -> str:
        text = text.replace("**", "")
        text = text.replace("__", "")
        text = text.replace("```", "")
        text = text.replace("##", "")
        text = text.replace("*", "")
        return text.strip()

    def _clean_word(self, word: str) -> str:
        if not word:
            return ""

        # Keep pure Arabic-script Kurdish words
        if re.fullmatch(r"[\u0600-\u06FF0-9]+", word):
            return word

        # Keep English proper nouns / tickers / abbreviations
        if re.fullmatch(r"[A-Za-z0-9.\-_/&]+", word):
            return word

        # Mixed word: keep Kurdish part if present, else keep plain English part if present
        kurdish_part = re.sub(r"[^\u0600-\u06FF0-9]", "", word)
        english_part = re.sub(r"[^A-Za-z0-9.\-_/&]", "", word)

        if kurdish_part:
            return kurdish_part
        if english_part:
            return english_part

        return ""

    def _clean_result(self, text: str) -> str:
        text = self._strip_markdown(text)

        # remove clearly forbidden scripts first
        text = self.forbidden_script_pattern.sub(" ", text)

        # keep only Arabic script, ASCII, digits, whitespace, and simple punctuation
        text = self.allowed_punctuation_pattern.sub(" ", text)

        # clean per-word
        words = text.split()
        cleaned_words = []

        for word in words:
            cleaned = self._clean_word(word)
            if cleaned:
                cleaned_words.append(cleaned)

        text = " ".join(cleaned_words)

        # normalize whitespace around punctuation
        text = re.sub(r"\s+([.,:%$€£()\/'\":؛،؟!+\-])", r"\1", text)
        text = re.sub(r"([(\-\/])\s+", r"\1", text)
        text = re.sub(r"\s+", " ", text).strip()

        # normalize multiple blank lines
        text = re.sub(r"\n\s*\n+", "\n\n", text)

        return text.strip()

    def _has_forbidden_script(self, text: str) -> bool:
        return bool(self.forbidden_script_pattern.search(text or ""))

    def _latin_word_count(self, text: str) -> int:
        if not text:
            return 0
        return len(re.findall(r"\b[A-Za-z][A-Za-z0-9.\-_/&]*\b", text))

    def _arabic_word_count(self, text: str) -> int:
        if not text:
            return 0
        return len(re.findall(r"[\u0600-\u06FF]+", text))

    def _looks_bad_output(self, text: str) -> bool:
        if not text:
            return True

        if self._has_forbidden_script(text):
            return True

        arabic_count = self._arabic_word_count(text)
        latin_count = self._latin_word_count(text)

        # Must contain meaningful Sorani body unless it is SKIP
        if arabic_count < 4:
            return True

        # Too much English usually means the model ignored the instruction
        if latin_count > max(6, arabic_count // 2):
            return True

        return False

    def _chat_sync(self, prompt: str) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            temperature=0.2,
            messages=[
                {"role": "user", "content": prompt}
            ],
        )
        return response.choices[0].message.content.strip()

    async def _chat(self, prompt: str) -> str:
        return await asyncio.to_thread(self._chat_sync, prompt)

    async def process(self, title: str, description: str = ""):
        try:
            # First attempt
            prompt = self._create_prompt(title, description, strict=False)
            result = await self._chat(prompt)

            result_upper = result.strip().upper()
            if result_upper == "SKIP" or result_upper.startswith("SKIP"):
                logger.info(f"⏭️ Skipped (not Forex relevant): {title[:60]}")
                return None

            cleaned = self._clean_result(result)

            # Retry once if output is polluted or low quality
            if self._looks_bad_output(cleaned):
                retry_prompt = self._create_prompt(title, description, strict=True)
                retry_result = await self._chat(retry_prompt)

                retry_upper = retry_result.strip().upper()
                if retry_upper == "SKIP" or retry_upper.startswith("SKIP"):
                    logger.info(f"⏭️ Skipped (not Forex relevant): {title[:60]}")
                    return None

                retry_cleaned = self._clean_result(retry_result)

                # Prefer retry if it is better
                if not self._looks_bad_output(retry_cleaned):
                    cleaned = retry_cleaned

            if not cleaned or len(cleaned) < 10:
                logger.warning(f"⚠️ Translation too short or empty: {title[:60]}")
                return None

            logger.info(f"✅ Translated: {title[:60]}")
            return cleaned

        except Exception as e:
            logger.error(f"Translator error: {e}")
            return None


_translator = SmartTranslator()


async def process_smart_news(title: str, description: str = ""):
    return await _translator.process(title, description)
