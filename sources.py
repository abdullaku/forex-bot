from economic_calendar import EconomicCalendar
from news import NewsScraper as NewsService


class SourcesManager:
    def __init__(self):
        self.calendar_service = EconomicCalendar()
        self.news_service = NewsService()

    async def fetch_calendar(self):
        return await self.calendar_service.fetch_calendar()

    async def fetch_all(self):
        return await self.news_service.fetch_all()
