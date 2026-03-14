import json
import logging
import aiohttp
from config import Config

logger = logging.getLogger(__name__)

async def translate_to_kurdish(article):
    prompt = f"""ئەم هەواڵە بکە بە کوردیی سۆرانی. تەنها JSON بدەرەوە بەبێ هیچ دەقی تر:
{{"title_ku": "ناونیشانی کوردی لێرە", "summary_ku": "پوختەی کوردی لێرە ٣ هەستە", "signal": null}}

ناونیشان: {article['title']}
پوختە: {article['summary'][:400]}"""

    try:
        async with aiohttp.ClientSession() as session:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={Config.GEMINI_API_KEY}"
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.1,
                    "maxOutputTokens": 500,
                    "responseMimeType": "application/json"
                }
            }
            async with session.post(url, headers={"Content-Type": "application/json"},
                json=payload, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    raw = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                    result = json.loads(raw)
                    article["title_ku"] = result.get("title_ku", article["title"])
                    article["summary_ku"] = result.get("summary_ku", article["summary"])
                    article["signal"] = result.get("signal", None)
                    logger.info(f"Translated: {article['title_ku'][:40]}")
                else:
                    logger.error(f"Gemini error: {resp.status}")
                    article["title_ku"] = article["title"]
                    article["summary_ku"] = article["summary"]
    except Exception as e:
        logger.error(f"Translation error: {e}")
        article["title_ku"] = article["title"]
        article["summary_ku"] = article["summary"]
    return article
