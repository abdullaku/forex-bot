import re
from datetime import datetime
from html import unescape


class NewsParser:
    FOREX_PAIRS = [
        "EUR/USD",
        "GBP/USD",
        "USD/JPY",
        "XAU/USD",
        "GOLD",
        "WTI",
        "OIL",
        "USD",
    ]

    def detect_pairs(self, text):
        return [pair for pair in self.FOREX_PAIRS if pair.upper() in text.upper()]

    def _clean_summary(self, raw: str) -> str:
        # ١. HTML entities کۆد بکەرەوە  &amp; → &  &lt; → <
        text = unescape(raw)
        # ٢. HTML tagەکان لادەبەین  <p>, <a>, <img> ...
        text = re.sub(r"<[^>]+>", " ", text)
        # ٣. فراوانی زیادە لادەبەین
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def _extract_image_url(self, item) -> str:
        # ١. <media:content url="...">
        media = item.find("media:content")
        if media and media.get("url"):
            return media["url"]

        # ٢. <media:thumbnail url="...">
        thumb = item.find("media:thumbnail")
        if thumb and thumb.get("url"):
            return thumb["url"]

        # ٣. <enclosure url="..." type="image/...">
        enclosure = item.find("enclosure")
        if enclosure and enclosure.get("type", "").startswith("image"):
            return enclosure.get("url", "")

        # ٤. <description> دەناوی <img src="..."> هەبێت
        desc = item.find("description")
        if desc:
            match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', str(desc))
            if match:
                return match.group(1)

        return ""

    def parse_rss_item(self, item, source_name, category):
        title = item.find("title").text.strip() if item.find("title") else ""
        raw_summary = item.find("description").text.strip() if item.find("description") else ""
        url = item.find("link").text.strip() if item.find("link") else ""

        # ✅ HTML لادەبەین لە summary پێش نێردن بۆ AI
        summary = self._clean_summary(raw_summary)

        image_url = self._extract_image_url(item)

        return {
            "title": title,
            "summary": summary[:500],
            "url": url,
            "source": source_name,
            "category": category,
            "pairs": self.detect_pairs(title + " " + summary),
            "image_url": image_url or None,
            "published_at": datetime.now().isoformat(),
        }
