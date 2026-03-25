import os
import re
import asyncio
import google.generativeai as genai
from groq import Groq

# ڕێکخستنی کلیلەکان
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

groq_client = Groq(api_key=GROQ_API_KEY)
genai.configure(api_key=GEMINI_API_KEY)
gemini_model = genai.GenerativeModel('gemini-1.5-flash')

def clean_text(text):
    """پاککردنەوەی دەق بۆ ڕێگری لە هەڵەی 400"""
    if not text: return ""
    cleaned = re.sub(r'[^\x20-\x7E]+', ' ', text) # تەنها کارەکتەری ستاندارد بۆ Groq
    return cleaned.strip()[:800]

async def process_smart_news(english_title):
    """هەڵسەنگاندن بە Groq و وەرگێڕان بە Gemini"""
    try:
        safe_title = clean_text(english_title)
        if not safe_title: return None

        # هەنگاوی یەکەم: Groq بۆ هەڵسەنگاندن (بێ سانسۆر)
        rating_prompt = f"Rate this financial news importance (1-10). Reply ONLY with the number: {safe_title}"
        
        try:
            # گۆڕینی مۆدێل بۆ mixtral کە خێراتر و وردترە بۆ ئەم کارە
            chat_completion = groq_client.chat.completions.create(
                messages=[{"role": "user", "content": rating_prompt}],
                model="mixtral-8x7b-32768", 
                timeout=15
            )
            rating_str = chat_completion.choices[0].message.content.strip()
            rating = int(''.join(filter(str.isdigit, rating_str[:5])) or 0)
        except Exception as e:
            print(f"⚠️ Groq Error: {e}")
            rating = 6 # نمرەیەکی مامناوەند ئەگەر Groq کاری نەکرد

        # هەنگاوی دووەم: ئەگەر نمرەکە ٥ یان زیاتر بوو (دەسەڵاتی تەواو بە AI)
        if rating >= 5:
            print(f"✅ AI Approved (Rating: {rating}): {safe_title}")
            
            translation_prompt = f"Translate this financial news to professional Kurdish Sorani for a Forex channel. Only provide the translation: {safe_title}"
            
            # بەکارهێنانی Gemini بۆ وەرگێڕانی خێرا
            response = gemini_model.generate_content(translation_prompt)
            return response.text.strip()
        
        else:
            print(f"📉 Low Priority (Rating: {rating}): {safe_title}")
            return None

    except Exception as e:
        print(f"❌ Error in Processor: {e}")
        return None

async def generate_daily_analysis(news_list):
    """کۆکەرەوەی ڕۆژانە بە Gemini"""
    try:
        if not news_list: return None
        prompt = f"Summarize these forex news into a professional Kurdish Sorani market sentiment: {news_list}"
        response = gemini_model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"❌ Daily Analysis Error: {e}")
        return None
