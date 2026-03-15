import json
import logging
import aiohttp
import re
from config import Config

logger = logging.getLogger(__name__)

def clean_html(text):
    text = re.sub(r'<[^>]+>', '', text)
    return text[:300].strip()

def extract_json(text):
    try:
        # ئەگەر ڕاستەوخۆ JSON بوو
        return json.loads(text)
    except:
        pass
    try:
        # ئەگەر لە ناو ``` دابوو
        match = re.search(r'\{.*?\}', text, re.DOTALL)
        if match:
            return json.loads(match.group())
    except:
        pass
    return None

async def translate_to_kurdish(article):
    title = article['title'][:100]
    summary = clean_html(article['summary'])
    
    prompt = f"""You are a Kurdish Sorani translator. Translate the news below to Kurdish Sorani.
Return ONLY a JSON object like this example:
{{"title_ku": "ناونیشانی کوردی", "summary_ku": "پوختەی کوردی لێرەدا", "signal": null}}

News Title: {title}
News Summary: {summary}

JSON:"""

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {Config.GROQ_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "openai/gpt-oss-120b",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 400,
                    "temperature": 0.1
                },
                timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    raw = data["choices"][0]["message"]["content"].strip()
                    logger.info(f"Raw response: {raw[:100]}")
                    result = extract_json(raw)
                    if result:
                        article["title_ku"] = result.get("title_ku", title)
                        article["summary_ku"] = result.get("summary_ku", summary)
                        article["signal"] = result.get("signal", None)
                        logger.info(f"✅ Translated: {article['title_ku'][:40]}")
                    else:
                        logger.error(f"JSON parse failed: {raw[:100]}")
                        article["title_ku"] = title
                        article["summary_ku"] = summary
                else:
                    logger.error(f"Groq error: {resp.status}")
                    article["title_ku"] = title
                    article["summary_ku"] = summary
    except Exception as e:
        logger.error(f"Translation error: {e}")
        article["title_ku"] = title
        article["summary_ku"] = summary
    return article
