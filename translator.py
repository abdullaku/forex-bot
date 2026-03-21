import aiohttp
import json
import re
from config import Config

def extract_json(text):
    try:
        return json.loads(text)
    except:
        pass
    try:
        match = re.search(r'\{.*?\}', text, re.DOTALL)
        if match:
            return json.loads(match.group())
    except:
        pass
    return None

async def translate_to_kurdish(article):
    title = article['title'][:100]
    summary = re.sub(r'<[^>]+>', '', article.get('summary', ''))[:300].strip()
    
    prompt = f"""You are a professional Kurdish Sorani translator.
STRICT RULES:
- Translate ONLY to Kurdish Sorani script
- NEVER use Arabic, Persian, Hindi, Urdu or any other language
- NEVER mix languages
- If a technical term has no Kurdish equivalent, use English
- Use ONLY these Kurdish characters: ئابپتجچحخدرزژسشعغفقکگلمنوهیەڵۆ

Return ONLY this JSON:
{{"title_ku": "کوردی سۆرانی", "summary_ku": "کوردی سۆرانی"}}

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
                    "model": "llama-3.3-70b-versatile",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 400,
                    "temperature": 0.1
                },
                timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    raw = data["choices"][0]["message"]["content"].strip()
                    result = extract_json(raw)
                    if result:
                        article["title_ku"] = result.get("title_ku", title)
                        article["summary_ku"] = result.get("summary_ku", summary)
                    else:
                        article["title_ku"] = title
                        article["summary_ku"] = summary
                else:
                    article["title_ku"] = title
                    article["summary_ku"] = summary
    except Exception as e:
        article["title_ku"] = title
        article["summary_ku"] = summary
    return article

async def generate_daily_analysis(articles):
    titles = "\n".join([f"- {a.get('title', '')}" for a in articles])
    prompt = f"""تۆ شارەزایەکی بازاڕی فۆرێکسی. ئەمە لیستی ناونیشانی هەواڵەکانی ئەمڕۆیە:
{titles}

تکایە شیکارییەکی قووڵ و کورت (Deep Analysis) بە زمانی کوردی بنووسە و ئەم ئیمۆجیانە بەکاربهێنە:
- بۆ دۆلار و ئەمریکا: 🇺🇸
- بۆ یۆرۆ و ئەوروپا: 🇪🇺
- بۆ پاوەند و بەریتانیا: 🇬🇧
- بۆ زێڕ: 🟡 یان 🏆
- بۆ نەوت: 🛢️
- بۆ هەواڵی ئەرێنی: ✅ یان 📈
- بۆ هەواڵی نەرێنی: ❌ یان 📉

شێوازی نووسین:
1. کورتەیەک لەسەر جووڵەی بازاڕی ئەمڕۆ.
2. کاریگەری ئەم هەواڵانە لەسەر (زێڕ، دۆلار، یان نەوت).
3. ئاڕاستەی پێشبینیکراو بۆ سبەینێ.

بە شێوازێکی پڕۆفیشناڵ بینووسە و لە کۆتاییدا بەم ئیمۆجییە دایبخە: 🏁
سەرەتا بنووسە: 📊 <b>شیکاری قووڵی بازاڕ (کۆتایی ڕۆژ)</b>"""

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {Config.GROQ_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "llama-3.3-70b-versatile",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 800,
                    "temperature": 0.3
                },
                timeout=aiohttp.ClientTimeout(total=60)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data["choices"][0]["message"]["content"].strip()
                else:
                    return "⚠️ ناتوانرێت شیکارییەکە دروست بکرێت"
    except Exception as e:
        return f"⚠️ ناتوانرێت شیکارییەکە دروست بکرێت: {str(e)}"
