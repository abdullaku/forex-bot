import os
import re # بۆ پاککردنەوەی دەق زیادکرا
import google.generativeai as genai
from groq import Groq

# ١. ڕێکخستنی کلیلەکان لە Render
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# ناساندنی کلاینتەکان
groq_client = Groq(api_key=GROQ_API_KEY)
genai.configure(api_key=GEMINI_API_KEY)

def clean_text(text):
    """پاککردنەوەی دەق لە هێما نامۆکان بۆ ئەوەی Groq هەڵە نەدات"""
    if not text: return ""
    # تەنها پیت و ژمارە و نیشانە سەرەکییەکان دەهێڵێتەوە
    cleaned = re.sub(r'[^\w\s\d\.\,\!\?\-\:]', '', text)
    return cleaned[:700] # کورتکردنەوە بۆ ٧٠٠ کارەکتەر

async def process_smart_news(english_title):
    try:
        # پاککردنەوەی دەقەکە پێش ناردن
        safe_title = clean_text(english_title)
        
        # هەنگاوی یەکەم: Groq بۆ هەڵسەنگاندن
        rating_prompt = f"Rate the importance of this financial news (1-10). Reply ONLY with the number: {safe_title}"
        
        try:
            chat_completion = groq_client.chat.completions.create(
                messages=[{"role": "user", "content": rating_prompt}],
                model="llama3-8b-8192",
                timeout=10 # کاتی دیاریکراو بۆ ئەوەی بۆتەکە گیر نەخوات
            )
            rating_str = chat_completion.choices[0].message.content.strip()
            rating = int(''.join(filter(str.isdigit, rating_str)))
        except Exception as groq_err:
            print(f"⚠️ Groq Error, using default rating 7: {groq_err}")
            rating = 7 # ئەگەر Groq کاری نەکرد، وادادەنێین هەواڵەکە گرنگە تاوەکو وەرگێڕانەکە نەفەوتێت

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

# فەنکشنی generate_daily_analysis وەک خۆیەتی...
