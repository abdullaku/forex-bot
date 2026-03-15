import json
import logging
import aiohttp
import re
from config import Config

logger = logging.getLogger(__name__)

def clean_html(text):
    text = re.sub(r'<[^>]+>', '', text)
    return text[:300].strip()

async def translate_to_kurdish(article):
    title = article['title'][:100]
    summary = clean_html(article['summary'])
    
    prompt = f"وەرگێڕانی ئەم هەواڵە بکە بۆ کوردیی سۆرانی. تەنها JSON بدەرەوە:\n{{\"title_ku\": \"ناونیشانی کوردی\", \"summary_ku\": \"پوختەی کوردی ٢ هەستە\", \"signal\": null}}\n\nناونیشان: {title}\nپوختە: {summary}"

    try:
        async with aiohttp.ClientSession() as session:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={Config.GEMINI_API_KEY}"
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.1, "maxOutputTokens": 300}
            }
            async with session.post(url, headers={"Content-Type": "application/json"},
                json=payload, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    raw = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                    if "```" in raw:
                        raw = raw.split("```")[1]
                        if raw.startswith("json"): raw = raw[4:]
                    result = json.loads(raw.strip())
                    article["title_ku"] = result.get("title_ku", title)
                    article["summary_ku"] = result.get("summary_ku", summary)
                    article["signal"] = result.get("signal", None)
                    logger.info(f"✅ Translated: {article['title_ku'][:40]}")
                else:
                    logger.error(f"Gemini error: {resp.status}")
                    article["title_ku"] = title
                    article["summary_ku"] = summary
    except Exception as e:
        logger.error(f"Translation error: {e}")
        article["title_ku"] = title
        article["summary_ku"] = summary
    return article
