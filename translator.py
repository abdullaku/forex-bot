import os
import google.generativeai as genai
from groq import Groq

# ١. ڕێکخستنی کلیلەکان لە Render
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# ناساندنی کلاینتەکان
groq_client = Groq(api_key=GROQ_API_KEY)
genai.configure(api_key=GEMINI_API_KEY)

async def process_smart_news(english_title):
    """
    ئەم فەنکشنە هەواڵ لە هەموو سەرچاوەکان وەردەگرێت، هەڵسەنگاندنی بۆ دەکات
    و ئەگەر گرنگ بوو بە Gemini وەری دەگێڕێت.
    """
    try:
        # هەنگاوی یەکەم: Groq بۆ هەڵسەنگاندنی هەموو جۆرە هەواڵێکی ئابووری
        rating_prompt = f"Rate the importance of this financial news for Forex, Gold, and Global Markets from 1 to 10. Reply ONLY with the number: {english_title}"
        
        chat_completion = groq_client.chat.completions.create(
            messages=[{"role": "user", "content": rating_prompt}],
            model="llama3-8b-8192",
        )
        
        rating_str = chat_completion.choices[0].message.content.strip()
        
        # دەرهێنانی تەنها ژمارەکە لە وەڵامەکەدا
        try:
            rating = int(''.join(filter(str.isdigit, rating_str)))
        except:
            rating = 0

        if rating >= 7:
            print(f"🔥 Important News (Rating: {rating}): {english_title}")
            
            # هەنگاوی دووەم: Gemini بۆ وەرگێڕانی کوردییەکی پڕۆفیشناڵ
            model = genai.GenerativeModel('gemini-1.5-flash')
            # لێرە پێمان وتووە کە هەواڵەکە داراییە (نەک تەنها بلومبێرگ)
            translation_prompt = f"Translate this financial news title to professional Kurdish Sorani for a Forex channel. Keep it concise: {english_title}"
            
            response = model.generate_content(translation_prompt)
            return response.text.strip()
            
        else:
            print(f"❄️ Skipping (Rating: {rating}): {english_title}")
            return None

    except Exception as e:
        print(f"❌ Error in Smart Processor: {e}")
        return None
        
