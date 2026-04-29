import re
import html


class TextFormatter:
    @staticmethod
    def clean_text(text: str) -> str:
        if not text:
            return ""

        text = text.strip()
        text = text.replace("**", "")
        text = text.replace("__", "")
        text = text.replace("```", "")
        text = text.replace("##", "")
        text = text.replace("*", "")

        # Remove unwanted old AI section labels if they ever appear.
        unwanted_lines = (
            "📰 هەواڵ:",
            "هەواڵ:",
            "📌 گرنگی بۆ Forex:",
            "گرنگی بۆ Forex:",
            "گرنگی بۆ فۆرێکس:",
            "⚠️ تێبینی:",
            "تێبینی:",
        )

        lines = []
        skip_rest = False

        for raw_line in text.splitlines():
            line = raw_line.strip()

            if any(marker in line for marker in unwanted_lines):
                if "گرنگی" in line or "Forex" in line or "فۆرێکس" in line or "تێبینی" in line:
                    skip_rest = True
                continue

            if skip_rest:
                continue

            if "signal" in line.lower() or "سیگناڵ" in line:
                continue

            lines.append(raw_line)

        text = "\n".join(lines)

        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"[ \t]{2,}", " ", text)

        return text.strip()

    @staticmethod
    def build_telegram_message(
        text: str,
        source: str,
        url: str,
        current_time: str,
        current_date: str,
    ) -> str:
        clean = TextFormatter.clean_text(text)

        safe_text = html.escape(clean)
        safe_source = html.escape(source)
        safe_url = html.escape(url, quote=True)

        return (
            f"{safe_text}\n\n"
            f"📌 {safe_source}\n"
            f'<a href="{safe_url}">🔗 سەرچاوەی فەرمی</a>\n'
            f"🕐 {current_time} | {current_date}"
        )

    @staticmethod
    def build_facebook_message(
        text: str,
        source: str,
        current_time: str,
        current_date: str,
    ) -> str:
        clean = TextFormatter.clean_text(text)

        return (
            f"{clean}\n\n"
            f"📌 {source}\n"
            f"🔗 سەرچاوەی فەرمی\n"
            f"🕐 {current_time} | {current_date}"
        )
