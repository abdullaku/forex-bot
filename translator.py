import os
import re
import asyncio
import google.generativeai as genai
from groq import Groq

# ڕێکخستنی کلیلەکان لە ژینگەی Render
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# ناساندنی کلاینتەکان
groq_client = Groq(api_key=GROQ_API_KEY)
genai.configure(api_key=GEMINI_API_KEY)
gemini_model = genai.GenerativeModel('gemini-1.5-flash')

def clean_text(text):
    """پاککردنەوەی دەق بۆ ڕێگری لە هەر هەڵەیەکی کارەکتەر"""
    if not text: return ""
    # لابردنی کارەکتەرە نائاساییەکان کە Groq پێی تێکدەچێت
    cleaned = re.sub(r'[^\x00-\x7F]+', ' ', text)
    return cleaned.strip()[:1000]

async def process_smart_news(english_title):
    """هەڵسەنگاندن بە بەهێزترین مۆدێلی خۆڕایی Groq و وەرگێڕان بە Gemini"""
    try:
        safe_title = clean_text(english_title)
        if not safe_title: return None

        # --- هەنگاوی یەکەم: Groq بۆ هەڵسەنگاندن (Llama 3.3 70B) ---
        rating = 0
        try:
            chat_completion = groq_client.chat.completions.create(
                messages=[
                    {
                        "role": "system", 
                        "content": "You are a financial news filter. Rate importance for Forex traders from 1 to 10. Respond with ONLY the number."
                    },
                    {
                        "role": "user", 
                        "content": f"Rate this: {safe_title}"
                    }
                ],
                model="llama-3.3-70b-versatile", # مۆدێلە بەهێز و خۆڕاییەکە
                temperature=0.1,
                max_tokens=5
            )
            response_text = chat_completion.choices[0].message.content.strip()
            # دەرهێنانی تەنها ژمارەکە
            rating = int(''.join(filter(str.isdigit, response_text)) or 0)
        except Exception as e:
            print(f"⚠️ Groq (Rating) Error: {e}")
            rating = 7  # نمرەیەکی دیفۆڵت ئەگەر سێرڤەرەکە لۆدی زۆر بوو

        # --- هەنگاوی دووەم: ئەگەر گرنگ بوو، وەرگێڕان بە Gemini ---
        if rating >= 6:
            print(f"✅ Approved by Groq (Rating: {rating})")
            
            try:
                translation_prompt = (
                    f"Translate this Forex news title to professional Kurdish Sorani. "
                    f"Keep financial terms accurate. News: {safe_title}"
                )
                
                # وەرگێڕان بە Gemini
                response = gemini_model.generate_content(translation_prompt)
                kurdish_text = response.text.strip()
                
                if kurdish_text:
                    return kurdish_text
            except Exception as e:
                print(f"⚠️ Gemini (Translation) Error: {e}")
                return None
        
        else:
            print(f"📉 Low Priority (Rating: {rating})")
            return None

    except Exception as e:
        print(f"❌ Processor Critical Error: {e}")
        return None

async def generate_daily_analysis(news_list):
    """کۆکەرەوەی ڕۆژانە بە Gemini"""
    try:
        if not news_list: return None
        prompt = f"Summarize these news items into a professional Kurdish Sorani market sentiment report: {news_list}"
        response = gemini_model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"❌ Daily Analysis Error: {e}")
        return None
