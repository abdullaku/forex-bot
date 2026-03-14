import json
import logging
import aiohttp
from config import Config

logger = logging.getLogger(__name__)

PROMPT = """تۆ یارمەتیدەری پسپۆڕی بازاری فۆرێکسیت.
هەواڵی خوارەوە بکە بە کوردیی سۆرانی و وەڵامت بدەرەوە تەنها بە JSON:
{{
  "title_ku": "ناونیشانی کوردی",
  "summary_ku": "پوختەی کوردی ٣-٥ هەستە",
  "signal": null
}}
سەرچاوە: {source}
ناونیشان: {title}
پوختە: {summary}"""

async def translate_to_kurdish(article):
    prompt = PROMPT.format(source=article['source'], title=article['title'], summary=article['summary'][:600])
    try:
        async with aiohttp.ClientSession() as session:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={Config.GEMINI_API_KEY}"
            async with session.post(url, headers={"Content-Type": "application/json"},
                json={"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0.3, "maxOutputTokens": 800}},
                timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    raw = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                    if "```" in raw:
                        raw = raw.split("```")[1]
                        if raw.startswith("json"): raw = raw[4:]
                    result = json.loads(raw.strip())
                    article["title_ku"] = result.get("title_ku", article["title"])
                    article["summary_ku"] = result.get("summary_ku", article["summary"])
                    article["signal"] = result.get("signal", None)
                else:
                    article["title_ku"] = article["title"]
                    article["summary_ku"] = article["summary"]
    except Exception as e:
        logger.error(f"Translation error: {e}")
        article["title_ku"] = article["title"]
        article["summary_ku"] = article["summary"]
    return article
