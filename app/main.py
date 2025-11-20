# persian_bot.py ────────────────────────────────────────────────────────────

# --------------------------------------------------------------------------- #
# بخش ۱: وارد کردن کتابخانه‌های مورد نیاز
# --------------------------------------------------------------------------- #
import os
import json
import asyncio
import openai

# کتابخانه‌های اصلی FastAPI برای ساخت وب‌سرویس
from fastapi import FastAPI, HTTPException, status, BackgroundTasks
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles


from .middleware import (
    GlobalErrorHandlerMiddleware, 
    RateLimitMiddleware
)

# Pydantic برای اعتبارسنجی و تعریف مدل‌های ورودی
from pydantic import BaseModel, Field

# کتابخانه dotenv برای خواندن متغیرها از فایل .env
from dotenv import load_dotenv


# توابع کمکی برای ارتباط با دیتابیس
from .db_per import user_exists, save_message, get_last_20_messages, load_prompt_from_file

# تنظیمات لاگینگ
from .logging_config import setup_logging, log_before_retry
import logging

setup_logging()
app_logger = logging.getLogger("app." + __name__)
openai_logger = logging.getLogger("openai." + __name__)

# کتابخانه Tenacity برای ایجاد مکانیزم تلاش مجدد (Retry)
from typing import Iterator,AsyncIterator
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# کلاس‌های خطای مشخص از کتابخانه OpenAI برای مدیریت خطاها
from openai import APITimeoutError, APIConnectionError, RateLimitError, APIError

# کتابخانه Redis برای ذخیره سازی داده‌ها
import redis
from .middleware import RateLimitMiddleware

# Import the chat router
from .routers.chat import router

# Import OpenAI client and prompt file paths
from .openai_client import client, NEW_USER_PROMPT_FILE, RETURNING_USER_PROMPT_FILE, GENERAL_PROMPT_FILE

# 1. Initialize Redis client
redis_client = redis.Redis(host='localhost', port=6379, db=0)


# --------------------------------------------------------------------------- #
# بخش ۳: ساخت اپلیکیشن FastAPI و نصب Middleware ها
# --------------------------------------------------------------------------- #
from .middleware import GlobalErrorHandlerMiddleware, AccessLogMiddleware, RateLimitMiddleware

app = FastAPI(title="Persian Chatbot")

# Serve static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Add route for the main page
@app.get("/")
async def root():
    return FileResponse("app/static/index.html")

# Include the chat router
app.include_router(router)

# --- نصب Middleware ها به ترتیب صحیح (از بیرون به درون) ---

# لایه ۱ (بیرونی‌ترین): مدیریت خطا
app.add_middleware(GlobalErrorHandlerMiddleware)

# لایه ۲: لاگینگ دسترسی، شناسه درخواست و زمان پردازش
app.add_middleware(AccessLogMiddleware)

# لایه ۳: مدیریت CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*", "http://localhost", "http://127.0.0.1:5500"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# لایه ۴ (درونی‌ترین): محدود کننده نرخ
app.add_middleware(
    RateLimitMiddleware, 
    redis_client=redis_client,
    requests_per_hour=35
)



# --------------------------------------------------------------------------- #
# بخش ۷: اجرای سرور
# --------------------------------------------------------------------------- #

# این بخش فقط زمانی اجرا می‌شود که فایل به صورت مستقیم اجرا شود (نه به عنوان ماژول)
if __name__ == "__main__":
    import uvicorn
    # اجرای سرور Uvicorn با قابلیت reload خودکار در صورت تغییر کد
    uvicorn.run("persian_bot:app", host="127.0.0.1", port=8000, reload=True)