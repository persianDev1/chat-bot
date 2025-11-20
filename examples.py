# example_openai_chat_format.py
"""
نمونه ساده برای نمایش فرمت ورودی و خروجی در چت‌بات OpenAI
بدون نیاز به اینترنت یا API Key
"""

# ورودی چت‌بات: مجموعه‌ای از پیام‌ها در قالب لیست از دیکشنری‌ها
messages = [
    {"role": "system", "content": " تو یک دستیار در سایت املاک هستی"},
    {"role": "user", "content": "سلام! میشه درباره فرم سرمایه‌گذاری توضیح بدی؟"},
]

# چاپ ورودی برای نمایش آموزشی
print("📤 پیام‌های ارسالی به مدل:")
print(messages)
print("-" * 60)

# ---- در حالت واقعی این بخش ارسال درخواست است ----
# from openai import OpenAI
# client = OpenAI(api_key="YOUR_API_KEY")
# response = client.chat.completions.create(
#     model="gpt-4o-mini",
#     messages=messages,
# )
# ---------------------------------------------

# پاسخ ساختگی برای نمایش در کلاس (شبیه پاسخ واقعی OpenAI)
fake_response = {
    "id": "chatcmpl-abc123",
    "object": "chat.completion",
    "created": 1730970000,
    "model": "gpt-4o-mini",
    "choices": [
        {
            "index": 0,
            "message": {
                "role": "assistant",
                "content": (
                    "فرم سرمایه‌گذاری شامل فیلدهایی مانند آدرس محل سکونت، "
                    "نوع خدمت سرمایه‌گذاری، حداقل و حداکثر سرمایه است. "
                    "پس از پر کردن فرم، اپراتورها برای بررسی با شما تماس خواهند گرفت."
                ),
            },
            "finish_reason": "stop",
        }
    ],
    "usage": {
        "prompt_tokens": 42,
        "completion_tokens": 33,
        "total_tokens": 75,
    },
}

# نمایش خروجی به صورت دیکشنری کامل
print("📥 پاسخ دریافتی از مدل:")
print(fake_response)
print("-" * 60)

# نمایش فقط محتوای متنی پاسخ
print("💬 متن پاسخ مدل:")
print(fake_response["choices"][0]["message"]["content"])
