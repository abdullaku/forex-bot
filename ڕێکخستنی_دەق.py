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
            f"📰 {safe_text}\n\n"
            f"📌 {safe_source}\n"
            f"🔗 <a href='{safe_url}'>بینە هەواڵەکە لە سەرچاوە</a>\n"
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
            f"📰 {clean}\n\n"
            f"📌 {source}\n"
            f"🕐 {current_time} | {current_date}"
        )
