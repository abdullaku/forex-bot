from news import NewsScraper as NewsService


class SourcesManager:
    """
    Official news manager only.

    This manager fetches news only from news.py:
    Fed, BLS, BEA, ECB, Eurostat, BoE, ONS, BoJ.

    ForexFactory / economic_calendar is no longer used here.
    """

    def __init__(self):
        self.news_service = NewsService()

    async def fetch_all(self):
        return await self.news_service.fetch_all()
