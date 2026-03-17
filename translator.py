import google.generativeai as genai
from config import Config

genai.configure(api_key=Config.GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

async def translate_to_kurdish(article):
    prompt = f"Translate the following finance news to Sorani Kurdish. Keep it professional and concise.\nTitle: {article['title']}\nSummary: {article['summary']}"
    try:
        response = model.generate_content(prompt)
        lines = response.text.strip().split('\n')
        article['title_ku'] = lines[0].replace('Title:', '').strip()
        article['summary_ku'] = "\n".join(lines[1:]).replace('Summary:', '').strip()
    except:
        article['title_ku'] = article['title']
        article['summary_ku'] = article['summary']
    return article

async def generate_daily_analysis(articles):
    titles = "\n".join([f"- {a['title']}" for a in articles])
    prompt = f"""
    تۆ شارەزایەکی بازاڕی فۆرێکسی. ئەمە لیستی ناونیشانی هەواڵەکانی ئەمڕۆیە:
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
    سەرەتا بنووسە: 📊 <b>شیکاری قووڵی بازاڕ (کۆتایی ڕۆژ)</b>
    """
    try:
        response = model.generate_content(prompt)
        # لێرەدا دەقەکە وەردەگرین و ئەگەر پێویست بکات پاکی دەکەینەوە
        analysis_text = response.text.strip()
        return analysis_text
    except Exception as e:
        return f"⚠️ ناتوانرێت شیکارییەکە دروست بکرێت: {str(e)}"
