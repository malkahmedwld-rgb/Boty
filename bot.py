import asyncio
import logging
import os
import random
from telethon import TelegramClient, events, Button
from pydub import AudioSegment

# إعدادات النظام
logging.basicConfig(
    format='%(asctime)s | %(levelname)s | %(message)s',
    level=logging.INFO
)
logger = logging.getLogger("SWIMA_Hybrid_System")

# بيانات حسابك الشخصي + توكن البوت (البيانات الجديدة)
api_id = 36474294
api_hash = '469e18e1369193bcc7f3c670a44abee3'
BOT_TOKEN = '8762389075:AAGAKqwPl3C73DUrQN2V7tz2MbUclIQBFFE'

# تشغيل العميلين (حسابك الشخصي والبوت)
user_client = TelegramClient('ai_library_session_2', api_id, api_hash)
bot_client = TelegramClient('bot_audio_session', api_id, api_hash)

pending_audios = {}
admin_id = None
bot_info = None

# دالة تحليل الصوت واستخراج اللقطات الحماسية
def process_audio(file_path, duration_mins):
    try:
        audio = AudioSegment.from_file(file_path)
        total_duration_ms = len(audio)
        
        clip_length_ms = duration_mins * 60 * 1000 
        step_ms = clip_length_ms // 2 
        
        if total_duration_ms < clip_length_ms:
            return [] 
            
        chunks = []
        for i in range(0, total_duration_ms - clip_length_ms + 1, step_ms):
            chunk = audio[i:i + clip_length_ms]
            chunks.append({
                "start": i,
                "chunk": chunk,
                "loudness": chunk.dBFS 
            })
            
        chunks = [c for c in chunks if c["loudness"] != float('-inf')]
        chunks.sort(key=lambda x: x["loudness"], reverse=True)
        
        top_chunks = chunks[:15]
        random.shuffle(top_chunks)
        
        selected_chunks = []
        for c in top_chunks:
            if len(selected_chunks) >= 3:
                break
            overlap = False
            for sc in selected_chunks:
                if abs(c["start"] - sc["start"]) < clip_length_ms:
                    overlap = True
                    break
            if not overlap:
                selected_chunks.append(c)
                
        output_files = []
        for i, c in enumerate(selected_chunks):
            out_path = f"highlight_{i+1}_{random.randint(1000,9999)}.mp3"
            c["chunk"].export(out_path, format="mp3")
            output_files.append(out_path)
            
        return output_files
        
    except Exception as e:
        logger.error(f"خطأ في معالجة الصوت: {e}")
        return []

# ----------------- أوامر البوت -----------------

@bot_client.on(events.NewMessage(pattern='/start'))
async def start_cmd(event):
    await event.reply("أهلاً بك! 🎧🔥\nأنا بوت حنين المدعوم بقوة حسابك الشخصي.\nأرسل لي أي مقطع (حتى لو كان بحجم 2 جيجابايت!) وسأستخرج لك اللقطات.")

@bot_client.on(events.NewMessage(func=lambda e: e.is_private and e.media and (e.audio or e.voice or getattr(e.media, 'document', None))))
async def audio_handler(event):
    pending_audios[event.chat_id] = event.message

    buttons = [
        [Button.inline("1 دقيقة", b"dur_1"), Button.inline("2 دقيقة", b"dur_2")],
        [Button.inline("3 دقائق", b"dur_3"), Button.inline("4 دقائق", b"dur_4")],
        [Button.inline("5 دقائق", b"dur_5")]
    ]
    await event.reply("⏱️ **اختر مدة كل مقطع حماسي تريد استخراجه:**", buttons=buttons)

@bot_client.on(events.CallbackQuery(pattern=b'dur_'))
async def dur_handler(event):
    duration = int(event.data.split(b'_')[1])
    chat_id = event.chat_id

    if chat_id not in pending_audios:
        await event.answer("انتهت الصلاحية، أرسل الملف مجدداً", alert=True)
        return

    audio_msg = pending_audios.pop(chat_id)
    await event.answer("تم اختيار المدة!")
    status_msg = await event.edit(f"⏳ تم اختيار ({duration} دقيقة).\nجاري التنزيل سراً عبر حسابك لتجاوز حظر 20 ميجا...")

    file_path = None
    try:
        # حسابك يبحث بنفسه عن آخر ملف في المحادثة وينزله!
        recent_msgs = await user_client.get_messages(bot_info.username, limit=10)
        user_msg = None
        for m in recent_msgs:
            if m.media and (m.audio or m.voice or getattr(m.media, 'document', None)):
                user_msg = m
                break
                
        if not user_msg:
            await status_msg.edit("❌ لم أتمكن من العثور على الملف لتنزيله.")
            return

        # حسابك الشخصي يقوم بتنزيل الملف
        save_path = f"temp_audio_{random.randint(1000, 99999)}.mp3"
        file_path = await user_client.download_media(user_msg, file=save_path)
        
        if not file_path:
            await status_msg.edit("❌ فشل التنزيل من سيرفرات تيليجرام.")
            return

        await status_msg.edit(f"✅ تم التنزيل بنجاح. جاري المونتاج واستخراج أفضل اللقطات...")

        # معالجة الصوت
        loop = asyncio.get_event_loop()
        clips = await loop.run_in_executor(None, process_audio, file_path, duration)

        if not clips:
            await status_msg.edit("❌ المقطع أقصر من المدة المطلوبة أو صامت.")
        else:
            await status_msg.edit(f"🔥 تم اقتناص {len(clips)} مقاطع! جاري الإرسال...")
            
            # إرسال المقاطع الجاهزة
            for i, clip in enumerate(clips):
                await bot_client.send_file(
                    chat_id,
                    clip,
                    caption=f"🔥 المقطع الحماسي رقم {i+1} (المدة: {duration} دقيقة)",
                    reply_to=audio_msg.id
                )
                os.remove(clip)

            await status_msg.edit("💜💜 صاي راني كملت المهمة بنجاح!")

        # تنظيف مساحة الهاتف
        if file_path and os.path.exists(file_path):
            os.remove(file_path)

    except Exception as e:
        await status_msg.edit(f"❌ حدث خطأ: {str(e)}")
        logger.error(f"Error: {e}")
        if file_path and os.path.exists(file_path):
            os.remove(file_path)

# الدالة الرئيسية
async def main():
    await user_client.start()
    await bot_client.start(bot_token=BOT_TOKEN)

    global admin_id, bot_info
    me = await user_client.get_me()
    admin_id = me.id
    bot_info = await bot_client.get_me()

    logger.info("🔥 نظام المونتاج الهجين الخالي من الأخطاء يعمل الآن!")
    
    await asyncio.gather(
        user_client.run_until_disconnected(),
        bot_client.run_until_disconnected()
    )

if __name__ == '__main__':
    asyncio.run(main())
