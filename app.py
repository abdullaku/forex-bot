async def process_article(
        self,
        article: dict,
        current_time: str,
        current_date: str,
    ) -> str:
        """
        Process one official news article.

        Returns a status string so process_news can log exactly what happened:
        - posted
        - already_posted
        - format_failed
        - send_failed
        - missing_url
        - missing_title
        """
        url = (article.get("url") or "").split("?")[0].strip()

        if not url:
            logger.warning("Article skipped because URL is missing")
            return "missing_url"

        title = article.get("title", "").strip()
        summary = article.get("summary", "").strip()
        source = article.get("source", "Official Source")
        currency = article.get("currency", "")

        if await is_posted(url):
            logger.info(f"News already posted: {source} - {title[:70] or url}")
            return "already_posted"

        if not title:
            logger.warning(f"Article skipped because title is missing: {url}")

            # ئەمە article ـی خراپە، بۆیە posted بکە تا هەموو جارێک دووبارە نەبێتەوە
            await mark_posted(url)
            return "missing_title"

        text = await process_smart_news(
            title=title,
            description=summary,
            source=source,
            currency=currency,
        )

        if not text:
            # گرنگ: لێرە mark_posted مەکە.
            # ئەگەر Groq/formatter temporary fail بوو، جارێکی تر retry دەکرێتەوە.
            logger.warning(
                f"Formatting failed, will retry later: {source} - {title[:70]}"
            )
            return "format_failed"

        telegram_msg = TextFormatter.build_telegram_message(
            text=text,
            source=source,
            url=url,
            current_time=current_time,
            current_date=current_date,
        )

        facebook_msg = TextFormatter.build_facebook_message(
            text=text,
            source=source,
            current_time=current_time,
            current_date=current_date,
        )

        tg_ok = False
        fb_ok = False

        try:
            await self.telegram.send_news(
                text=telegram_msg,
                image_url=article.get("image_url"),
            )
            tg_ok = True
            logger.info(f"Telegram posted: {source} - {title[:70]}")
        except Exception as e:
            logger.error(f"Telegram error: {type(e).__name__}: {e}")

        try:
            await self.facebook.post(
                text=facebook_msg,
                image_url=article.get("image_url"),
                link_url=url,
            )
            fb_ok = True
            logger.info(f"Facebook posted: {source} - {title[:70]}")
        except Exception as e:
            logger.error(f"Facebook error: {type(e).__name__}: {e}")

        if tg_ok or fb_ok:
            await mark_posted(url)
            return "posted"

        logger.warning(
            f"News send failed on all channels, will retry later: {source} - {title[:70]}"
        )
        return "send_failed"

    async def process_news(self, current_time: str, current_date: str) -> None:
        articles = await self.scraper.fetch_all()

        if not articles:
            logger.info("No official news found from sources")
            return

        logger.info(f"Found {len(articles)} official news items")

        stats = {
            "posted": 0,
            "already_posted": 0,
            "format_failed": 0,
            "send_failed": 0,
            "missing_url": 0,
            "missing_title": 0,
        }

        for article in articles:
            status = await self.process_article(
                article=article,
                current_time=current_time,
                current_date=current_date,
            )

            stats[status] = stats.get(status, 0) + 1

            # تەنها کاتێک sleep بکە کە بەڕاستی پۆست کرا
            if status == "posted":
                await asyncio.sleep(self.config.POST_DELAY)

        logger.info(
            "News summary: "
            f"posted={stats.get('posted', 0)} | "
            f"already_posted={stats.get('already_posted', 0)} | "
            f"format_failed={stats.get('format_failed', 0)} | "
            f"send_failed={stats.get('send_failed', 0)} | "
            f"missing_url={stats.get('missing_url', 0)} | "
            f"missing_title={stats.get('missing_title', 0)}"
        )
