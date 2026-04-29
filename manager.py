from news import NewsScraper as NewsService
from fxstreet_news import FXStreetNewsService


class SourcesManager:
    """
    News manager.

    Sections:
    1) Official macro news:
       Fed, BLS, BEA, ECB, Eurostat, BoE, ONS, BoJ.

    2) Forex market news:
       FXStreet, handled separately from official sources.

    ForexFactory / economic_calendar is not used here.
    """

    def __init__(self):
        self.news_service = NewsService()
        self.fxstreet_service = FXStreetNewsService()

    async def fetch_all(self):
        official_articles = await self.news_service.fetch_all()
        fxstreet_articles = await self.fxstreet_service.fetch_all()
        return official_articles + fxstreet_articles
