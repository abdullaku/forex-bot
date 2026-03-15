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
    
    prompt = f"""Translate this news to Kurdish Sorani language. Return ONLY this JSON format, no other text:
{{"title_ku": "translated title here", "summary_ku": "2 sentence summary in Kurdish Sorani here", "signal": null}}

Title: {title}
Summary: {summary}"""

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {Config.GROQ_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "meta-llama/llama-4-maverick-17b-128e-instruct",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 300,
                    "temperature": 0.1
                },
                timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    raw = data["choices"][0]["message"]["content"].strip()
                    if "```" in raw:
                        raw = raw.split("```")[1]
                        if raw.startswith("json"): raw = raw[4:]
                    result = json.loads(raw.strip())
                    article["title_ku"] = result.get("title_ku", title)
                    article["summary_ku"] = result.get("summary_ku", summary)
                    article["signal"] = result.get("signal", None)
                    logger.info(f"✅ Translated: {article['title_ku'][:40]}")
                else:
                    logger.error(f"Groq error: {resp.status}")
                    article["title_ku"] = title
                    article["summary_ku"] = summary
    except Exception as e:
        logger.error(f"Translation error: {e}")
        article["title_ku"] = title
        article["summary_ku"] = summary
    return article
