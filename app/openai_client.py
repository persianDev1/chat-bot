# app/openai_client.py ───────────────────────────────────────────────────────

import os
import logging
from openai import AsyncOpenAI # ✅ استفاده از نسخه Async
from dotenv import load_dotenv

# تنظیم لاگر برای اینکه اگر فایل پیدا نشد خبر بدهد
logger = logging.getLogger("openai." + __name__)

# --------------------------------------------------------------------------- #
# بخش ۱: پیدا کردن و لود کردن فایل .env (ایمن شده)
# --------------------------------------------------------------------------- #

# لیست مسیرهای احتمالی فایل .env
candidate_paths = (
    os.path.join(os.path.dirname(__file__), '..', '.env'), # یک پوشه عقب‌تر (روت پروژه)
    os.path.join(os.path.dirname(__file__), '.env')        # کنار همین فایل
)

# ✅ اصلاح: استفاده از مقدار پیش‌فرض None برای جلوگیری از StopIteration
dotenv_path = next(
    (p for p in candidate_paths if os.path.exists(p)), 
    None
)

if dotenv_path:
    load_dotenv(dotenv_path)
    # logger.info(f"Loaded configuration from: {dotenv_path}")
else:
    # اگر فایل پیدا نشد، فقط هشدار می‌دهیم (شاید متغیرها در سیستم‌عامل ست شده باشند)
    logger.warning("⚠️ No .env file found! Trying to use system environment variables.")


# --------------------------------------------------------------------------- #
# بخش ۲: ساخت کلاینت OpenAI
# --------------------------------------------------------------------------- #

# دریافت کلیدها
api_key = os.getenv("OPENAI_API_KEY")
base_url = os.getenv("OPENAI_BASE_URL")

if not api_key:
    logger.error("❌ OPENAI_API_KEY is missing! The chatbot will fail.")

# Create OpenAI client (Async Version)
client = AsyncOpenAI(
    api_key=api_key,
    base_url=base_url
)

# --------------------------------------------------------------------------- #
# بخش ۳: مسیر فایل‌های پرامپت
# --------------------------------------------------------------------------- #

ROOT = os.path.join("knowledgebase")
NEW_USER_PROMPT_FILE = os.path.join(ROOT, "prompt_new_user.txt")
RETURNING_USER_PROMPT_FILE = os.path.join(ROOT, "prompt_returning_user.md")
GENERAL_PROMPT_FILE = os.path.join(ROOT, "general_amlak_promt.md")