import os
import openai
from dotenv import load_dotenv

# 0. خواندن متغیرها از فایل .env
# اسکریپت در مکان‌های رایج زیر به دنبال فایل می‌گردد:

# مکان ۱: ریشه اصلی پروژه (مثلا: F:/tools/sy/persian_bot/.env)
project_root_env = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '.env'))

# مکان ۲: داخل پوشه app (مثلا: F:/tools/sy/persian_bot/app/.env)
api_dir_env = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '.env'))

dotenv_path = None
if os.path.exists(project_root_env):
    dotenv_path = project_root_env
elif os.path.exists(api_dir_env):
    dotenv_path = api_dir_env

if dotenv_path:
    load_dotenv(dotenv_path=dotenv_path)
    print(f"✅ فایل .env در مسیر '{dotenv_path}' پیدا و بارگذاری شد.")
else:
    print("❌ خطا: فایل .env پیدا نشد.")
    print("   اسکریپت در مسیرهای زیر به دنبال آن گشت:")
    print(f"   1. {project_root_env}")
    print(f"   2. {api_dir_env}")
    print("\n   لطفاً مطمئن شوید فایل .env شما در یکی از این مسیرها قرار دارد و نام آن دقیقاً '.env' است.")
    # اسکریپت ادامه می‌دهد تا متغیرهای سیستمی را چک کند

# 1. خواندن کلید و آدرس پایه از متغیرهای محیطی
api_key = os.getenv("OPENAI_API_KEY")
base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")

print("\n--- مرحله ۱: خواندن متغیرهای محیطی ---")
if api_key and "sk-" in api_key:
    print(f"✅ کلید OPENAI_API_KEY با موفقیت بارگذاری شد. [شروع کلید: {api_key[:6]}...]")
else:
    print("❌ خطا: کلید OPENAI_API_KEY پیدا نشد یا نامعتبر است.")
    print("   لطفاً فایل .env یا متغیرهای محیطی سیستم خود را بررسی کنید.")
    exit()

print(f"✅ آدرس پایه OPENAI_BASE_URL روی: {base_url} تنظیم شده است.")
print("-" * 40)


# 2. ساخت کلاینت OpenAI
try:
    client = openai.OpenAI(api_key=api_key, base_url=base_url)
    print("--- مرحله ۲: ساخت کلاینت OpenAI ---")
    print("✅ کلاینت با موفقیت ساخته شد.")
    print("-" * 40)
except Exception as e:
    print(f"❌ خطا: ساخت کلاینت OpenAI ناموفق بود: {e}")
    exit()


# 3. ارسال یک پیام تستی ساده
print("--- مرحله ۳: ارسال پیام تست ---")
print("پرسش: 'سلام، شما کی هستید؟'")

try:
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello, who are you?"}
        ],
        temperature=0,
        max_tokens=50 
    )
    
    assistant_message = response.choices[0].message.content
    print("\n✅ موفقیت! پاسخ از API دریافت شد:")
    print("-" * 20)
    print(assistant_message)
    print("-" * 20)

except openai.AuthenticationError as e:
    print("\n❌ خطای احراز هویت:")
    print("   کلید API ارائه شده نادرست یا منقضی شده است.")
    print(f"   جزئیات: {e}")

except openai.APIConnectionError as e:
    print("\n❌ خطای اتصال:")
    print("   اتصال به API برقرار نشد. شبکه یا آدرس پایه را بررسی کنید.")
    print(f"   جزئیات: {e}")
    
except Exception as e:
    print(f"\n❌ یک خطای غیرمنتظره رخ داد: {e}")
