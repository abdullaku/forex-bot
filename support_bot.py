"""
KurdTrader Support Bot
======================
- AI وەڵام دەداتەوە بە کوردی دەربارەی فۆرێکس و کەناڵ
- Human Takeover: ئادمین دەتوانێت خۆی قسە بکات لەجیاتی AI
- ئادمین ئاگادار دەکرێتەوە کاتێک کریار داوای پەیوەندی کرد
"""

import asyncio
import logging
from collections import defaultdict

from groq import Groq
from telegram import Update, Bot
from telegram.ext import (
    Application,
    MessageHandler,
    CommandHandler,
    filters,
    ContextTypes,
)

from translator import TranslatorConfig

logger = logging.getLogger(__name__)

# ── ئادمین ──────────────────────────────────────────────────────────────────
ADMIN_ID = 2065036390  # abdulla_botani

# ── System Prompt ────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """تۆ یاریدەدەری پسپۆڕی کەناڵی KurdTrader ی (@KurdTraderKRD).

زانیارییەکانت:
- کەناڵی KurdTrader بە بەشداری فۆرێکس و بازاڕی داراییەکان کاردەکات
- نرخی زێڕ (XAU/USD)، نەوتی برێنت، و دینارێ عێراقی بڵاو دەکرێتەوە
- هەواڵی ئابووری جیهانی بە کوردی سۆرانی دەنووسرێت
- کەناڵەکە بۆ فۆرێکسەران و سەرمایەگوزاران ئامادە کراوە

ئەرکەکانت:
- وەڵامدانەوەی پرسیارەکان دەربارەی فۆرێکس، زێڕ، نەوت، دینار، و بازاڕی داراییەکان
- ڕوونکردنەوەی تەرمینەلۆژی فینانسی
- زانیاری دەربارەی کەناڵەکە بدەرەوە

زمان:
- بە هەمان زمانی کریار وەڵام بدەرەوە (کوردی، عەرەبی، ئینگلیزی)
- ئەگەر کوردی نووسی، بە کوردی سۆرانی وەڵام بدەرەوە

سنووری وەڵامدانەوە:
- ئەگەر پرسیار دەرەوەی فۆرێکس و بازاڕی داراییەکان بوو، بە نەرمی ڕەتی بکەرەوە
- ئەگەر کریار داوای قسەکردن لەگەڵ ئادمین یان مرۆڤ کرد، بڵێ: "باشە، چاوەڕێ بکە ئادمین بەم زووانە دێت ✅"

شێواز:
- کورت و ڕوون
- پسپۆڕانە بەلام ئاسان
- بەبێ ئیموجیی زیادە"""

# ── State ────────────────────────────────────────────────────────────────────
# مێژووی گفتوگۆ بەرای هەر کەسێک
_histories: dict[int, list[dict]] = defaultdict(list)

# کریارەکانی کە ئادمین تەیکئۆڤەری کردووە
_takeover_active: set[int] = set()

# ئادمین ئێستا لەگەڵ کێ قسە دەکات
_admin_chatting_with: int | None = None

MAX_HISTORY = 20


# ── AI ───────────────────────────────────────────────────────────────────────
def _ask_groq(user_id: int, user_message: str) -> str:
    try:
        client = Groq(api_key=TranslatorConfig.API_KEY)

        history = _histories[user_id]
        history.append({"role": "user", "content": user_message})
        if len(history) > MAX_HISTORY:
            _histories[user_id] = history[-MAX_HISTORY:]

        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + _histories[user_id]

        response = client.chat.completions.create(
            model=TranslatorConfig.MODEL,
            temperature=0.4,
            max_tokens=500,
            messages=messages,
        )

        reply = response.choices[0].message.content.strip()
        _histories[user_id].append({"role": "assistant", "content": reply})
        return reply

    except Exception as e:
        logger.error(f"Groq support error: {e}")
        return "ببورە، کێشەیەک هەیە. تکایە چەند خولەکێک دواتر هەوڵ بدەرەوە."


# ── Handlers ─────────────────────────────────────────────────────────────────
async def _handle_user_dm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """پەیامی کریار وەردەگرێت"""
    if not update.message or not update.message.text:
        return

    user_id = update.effective_user.id
    username = update.effective_user.first_name or "کریار"
    text = update.message.text.strip()

    # ئەگەر ئادمین تەیکئۆڤەر کردووە → فۆرواردی بکە بۆ ئادمین
    if user_id in _takeover_active:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"👤 <b>{username}</b> [{user_id}]:\n{text}",
            parse_mode="HTML",
        )
        return

    # تایپینگ نیشان بدە
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    # AI وەڵام دەداتەوە
    reply = await asyncio.to_thread(_ask_groq, user_id, text)
    await update.message.reply_text(reply)

    # ئەگەر AI گوتی "ئادمین بەم زووانە دێت" → ئادمین ئاگادار بکەرەوە
    if "ئادمین بەم زووانە دێت" in reply or "چاوەڕێ بکە" in reply:
        await _notify_admin(context.bot, user_id, username, text)


async def _notify_admin(bot: Bot, user_id: int, username: str, last_msg: str) -> None:
    """ئادمین ئاگادار دەکرێتەوە"""
    try:
        await bot.send_message(
            chat_id=ADMIN_ID,
            text=(
                f"🔔 <b>کریاری نوێ داوای پەیوەندی کردووە</b>\n\n"
                f"👤 ناو: <b>{username}</b>\n"
                f"🆔 ID: <code>{user_id}</code>\n"
                f"💬 پەیام: {last_msg}\n\n"
                f"بۆ تەیکئۆڤەر: /takeover_{user_id}\n"
                f"بۆ بینینی مێژوو: /history_{user_id}"
            ),
            parse_mode="HTML",
        )
    except Exception as e:
        logger.error(f"Admin notify error: {e}")


async def _handle_admin_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """پەیامی ئادمین — فۆرواردی بکە بۆ کریار"""
    if not update.message or not update.message.text:
        return

    global _admin_chatting_with

    if _admin_chatting_with is None:
        await update.message.reply_text(
            "⚠️ ئێستا لەگەڵ هیچ کریارێک نەیت.\n"
            "بۆ تەیکئۆڤەر: /takeover_[ID]"
        )
        return

    text = update.message.text.strip()
    user_id = _admin_chatting_with

    try:
        await context.bot.send_message(chat_id=user_id, text=text)
        await update.message.reply_text("✅ نێردرا")
    except Exception as e:
        await update.message.reply_text(f"❌ هەڵە: {e}")


async def _cmd_takeover(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/takeover_[user_id] — ئادمین کۆنترۆڵ دەگرێت"""
    global _admin_chatting_with

    if update.effective_user.id != ADMIN_ID:
        return

    cmd = update.message.text
    try:
        user_id = int(cmd.split("_")[-1])
    except ValueError:
        await update.message.reply_text("❌ فۆرمات هەڵەیە. نموونە: /takeover_123456789")
        return

    _takeover_active.add(user_id)
    _admin_chatting_with = user_id

    await update.message.reply_text(
        f"✅ تەیکئۆڤەر چالاک بوو بۆ کریاری [{user_id}]\n"
        f"ئێستا هەموو پەیامێک بۆ کریارەکە دەچێت.\n"
        f"بۆ کۆتاییکردن: /done"
    )

    # کریار ئاگادار بکەرەوە
    try:
        await context.bot.send_message(
            chat_id=user_id,
            text="✅ ئادمین پەیوەندی کردووە. ئێستا دەتوانیت قسە بکەیت."
        )
    except Exception as e:
        logger.error(f"Notify user error: {e}")


async def _cmd_done(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/done — ئادمین تەیکئۆڤەر کۆتایی دێنێت"""
    global _admin_chatting_with

    if update.effective_user.id != ADMIN_ID:
        return

    if _admin_chatting_with is None:
        await update.message.reply_text("⚠️ تەیکئۆڤەری چالاک نییە.")
        return

    user_id = _admin_chatting_with
    _takeover_active.discard(user_id)
    _admin_chatting_with = None

    await update.message.reply_text(f"✅ تەیکئۆڤەر کۆتایی هات. AI دووبارە چالاک بوو.")

    try:
        await context.bot.send_message(
            chat_id=user_id,
            text="سوپاس بۆ پەیوەندیکردن! ئەگەر پرسیاری تر هەبوو، خۆشحاڵ دەبم یاریت بدەم. 🙂"
        )
    except Exception as e:
        logger.error(f"Done notify error: {e}")


async def _cmd_history(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/history_[user_id] — مێژووی گفتوگۆ"""
    if update.effective_user.id != ADMIN_ID:
        return

    cmd = update.message.text
    try:
        user_id = int(cmd.split("_")[-1])
    except ValueError:
        await update.message.reply_text("❌ فۆرمات هەڵەیە.")
        return

    history = _histories.get(user_id, [])
    if not history:
        await update.message.reply_text("مێژووی گفتوگۆ بەردەست نییە.")
        return

    lines = []
    for m in history[-10:]:  # کۆتا ١٠ پەیام
        role = "👤 کریار" if m["role"] == "user" else "🤖 بۆت"
        lines.append(f"{role}:\n{m['content']}")

    await update.message.reply_text("\n\n".join(lines))


async def _cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/start"""
    await update.message.reply_text(
        "سڵاو! 👋 بەخێربێیت بۆ KurdTrader Support.\n\n"
        "دەتوانیت پرسیارەکانت دەربارەی فۆرێکس، زێڕ، نەوت، و دینار بنێریت.\n\n"
        "چۆن یاریت بدەم؟"
    )


# ── Main Class ───────────────────────────────────────────────────────────────
class SupportBot:
    def __init__(self, token: str):
        self.token = token
        self.app = None

    async def start(self) -> None:
        logger.info("🤖 SupportBot: دەستی پێکرد")

        self.app = Application.builder().token(self.token).build()

        # کۆمەندەکان
        self.app.add_handler(CommandHandler("start", _cmd_start))
        self.app.add_handler(
            MessageHandler(
                filters.Regex(r"^/takeover_\d+$") & filters.User(ADMIN_ID),
                _cmd_takeover,
            )
        )
        self.app.add_handler(
            MessageHandler(
                filters.Regex(r"^/history_\d+$") & filters.User(ADMIN_ID),
                _cmd_history,
            )
        )
        self.app.add_handler(
            CommandHandler("done", _cmd_done, filters=filters.User(ADMIN_ID))
        )

        # پەیامی ئادمین (DM بۆ بۆت)
        self.app.add_handler(
            MessageHandler(
                filters.TEXT & filters.ChatType.PRIVATE & filters.User(ADMIN_ID),
                _handle_admin_message,
            )
        )

        # پەیامی کریار (DM بۆ بۆت)
        self.app.add_handler(
            MessageHandler(
                filters.TEXT & filters.ChatType.PRIVATE,
                _handle_user_dm,
            )
        )

        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling(drop_pending_updates=True)

        logger.info("🤖 SupportBot: گوێگرتن دەستی پێکرد")

    async def stop(self) -> None:
        if self.app:
            await self.app.updater.stop()
            await self.app.stop()
            await self.app.shutdown()
