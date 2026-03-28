from datetime import datetime


class پالێوەریهەواڵService:
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

    def parse_rss_item(self, item, source_name, category):
        title = item.find("title").text.strip() if item.find("title") else ""
        summary = item.find("description").text.strip() if item.find("description") else ""
        url = item.find("link").text.strip() if item.find("link") else ""

        return {
            "title": title,
            "summary": summary[:500],
            "url": url,
            "source": source_name,
            "category": category,
            "pairs": self.detect_pairs(title + " " + summary),
            "published_at": datetime.now().isoformat(),
        }
