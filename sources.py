from ڕۆژمێری_ئابووری import ڕۆژمێریئابووریService
from سەرچاوەی_هەواڵ import سەرچاوەیهەواڵService


class NewsScraper:
    def __init__(self):
        self.calendar_service = ڕۆژمێریئابووریService()
        self.news_service = سەرچاوەیهەواڵService()

    async def fetch_calendar(self):
        return await self.calendar_service.fetch_calendar()

    async def fetch_all(self):
        return await self.news_service.fetch_all()
