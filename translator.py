import os
import groq # بۆ هەڵسەنگاندن
import google.generativeai as genai # بۆ وەرگێڕان

# ڕێکخستنی کلیلەکان (دڵنیابە لە Render دانراون)
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

client_groq = groq.Groq(api_key=GROQ_API_KEY)
genai.configure(api_key=GEMINI_API_KEY)
gemini_model = genai.GenerativeModel('gemini-1.5-flash')

def evaluate_news(text):
    """هەڵسەنگاندنی هەواڵەکە لە ڕێگەی Groq و لابردنی هەموو سانسۆرەکان"""
    try:
        prompt = f"""
        Analyze this news and give it a score from 0 to 10 based on its importance to Forex and Economy.
        Respond ONLY with the number.
        News: {text[:1000]}
        """
        response = client_groq.chat.completions.create(
            model="mixtral-8x7b-32768",
            messages=[{"role": "user", "content": prompt}]
        )
        score = response.choices[0].message.content.strip()
        return float(''.join(filter(str.isdigit, score)) or 0)
    except Exception as e:
        print(f"Groq Error: {e}")
        return 0

def translate_to_kurdish(text):
    """وەرگێڕانی هەواڵەکە لە ڕێگەی Gemini"""
    try:
        prompt = f"Translate this financial news into professional Sorani Kurdish: {text}"
        response = gemini_model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"Gemini Error: {e}")
        return None

def process_news(news_text):
    # هەنگاوی ١: هەڵسەنگاندن بە Groq (بێ سانسۆر)
    score = evaluate_news(news_text)
    
    # هەنگاوی ٢: ئەگەر هەواڵەکە گرنگ بوو (بۆ نموونە سەروو ٥) بینێرە بۆ وەرگێڕان
    if score >= 5: # دەتوانی ئەم نمرەیە بە کەیفی خۆت بگۆڕیت
        kurdish_text = translate_to_kurdish(news_text)
        return kurdish_text, score
    
    return None, score
