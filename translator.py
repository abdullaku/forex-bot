import os
import re
import google.generativeai as genai
from groq import Groq

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

groq_client = Groq(api_key=GROQ_API_KEY)
genai.configure(api_key=GEMINI_API_KEY)

def clean_text(text):
    """پاککردنەوەی دەق - تەنها کارەکتەرە زیانبەخشەکان دەسڕێتەوە"""
    if not text:
        return ""
    # تەنها null bytes و کارەکتەرە کۆنترۆڵەکان دەسڕێتەوە، کوردی/عەرەبی دەمێنێتەوە
    cleaned = text.replace('\x00', '').strip()
    cleaned = re.sub(r'[\x01-\x08\x0b\x0c\x0e-\x1f\x7f]', '', cleaned)
    cleaned = cleaned[:700]
    if len(cleaned) < 5:
        return ""
    return cleaned

async def process_smart_news(english_title):
    try:
        safe_title = clean_text(english_title)

        if not safe_title:
            return None

        # هەنگاوی یەکەم: Groq بۆ هەڵسەنگاندن
        rating_prompt = f"Rate the importance of this financial news (1-10). Reply ONLY with the number: {safe_title}"

        try:
            chat_completion = groq_client.chat.completions.create(
                messages=[{"role": "user", "content": rating_prompt}],
                model="llama3-8b-8192",
                timeout=10
            )
            rating_str = chat_completion.choices[0].message.content.strip()
            rating = int(''.join(filter(str.isdigit, rating_str[:5])))
        except Exception as groq_err:
            print(f"⚠️ Groq Error, using default rating 7: {groq_err}")
            rating = 7

        if rating >= 7:
            print(f"🔥 Processing News (Rating: {rating}): {safe_title}")

            # هەنگاوی دووەم: Gemini بۆ وەرگێڕان
            model = genai.GenerativeModel('gemini-1.5-flash')
            translation_prompt = f"Translate this financial news to professional Kurdish Sorani for a Forex channel: {safe_title}"

            response = model.generate_content(translation_prompt)
            return response.text.strip()

        else:
            print(f"❄️ Skipping (Rating: {rating}): {safe_title}")
            return None

    except Exception as e:
        print(f"❌ Critical Error in Smart Processor: {e}")
        return None

async def generate_daily_analysis(news_list):
    try:
        if not news_list:
            return None

        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = f"Summarize these forex news into a brief daily market sentiment in Kurdish Sorani. Make it professional: {news_list}"

        response = model.generate_content(prompt)
        return response.text.strip()

    except Exception as e:
        print(f"❌ Error in Daily Analysis: {e}")
        return None
