# Persian Bot - ربات چت فارسی

ربات چت هوشمند با پشتیبانی از زبان فارسی برای ارتباط طبیعی و روان.

## 🚀 راه‌اندازی پروژه

### 1. پیش‌نیازها
- Python 3.8 یا بالاتر
- pip (مدیر بسته Python)

### 2. ایجاد محیط مجازی (Virtual Environment)

```bash
# ایجاد محیط مجازی
python -m venv venv

# فعال‌سازی محیط مجازی (Windows)
venv\Scripts\activate


### 3. نصب نیازمندی‌ها

```bash
# نصب بسته‌های مورد نیاز
pip install -r requirements.txt
```

### 4. اجرای سرور توسعه

```bash
# اجرای سرور با uvicorn
uvicorn app.main:app --reload
venv\Scripts\python.exe -m uvicorn app.main:app --reload
```


### 5. دسترسی به ربات

پس از اجرای سرور، به آدرس زیر مراجعه کنید:
```
http://localhost:8000
```

## 📁 ساختار پروژه

```
persian_bot/
├── app/
│   ├── main.py          # نقطه ورودی اصلی برنامه
│   ├── openai_client.py # کلاینت OpenAI
│   ├── database.py      # مدیریت پایگاه داده
│   ├── middleware.py    # میان‌افزارهای برنامه
│   ├── routers/
│   │   └── chat.py      # مسیرهای چت
│   └── static/          # فایل‌های استاتیک
│       ├── index.html
│       ├── css/
│       └── js/
├── requirements.txt     # لیست بسته‌های مورد نیاز
└── README.md           # این فایل
```

## ⚙️ پیکربندی

### متغیرهای محیطی

پیش از اجرای برنامه، متغیرهای زیر را تنظیم کنید:

- `OPENAI_API_KEY`: کلید API OpenAI
- `DATABASE_URL`: آدرس پایگاه داده (اختیاری)

در Windows:
```cmd
set OPENAI_API_KEY=your_api_key_here
```

در Linux/macOS:
```bash
export OPENAI_API_KEY=your_api_key_here
```

## 🛠️ توسعه

### اجرای تست‌ها

```bash
# اجرای تست‌ها (در صورت وجود)
python -m pytest
```

### فرمت‌دهی کد

```bash
# فرمت‌دهی با black
black .

# چک کردن با pylint
pylint app/
```

## 📞 پشتیبانی

در صورت بروز هرگونه مشکل یا سوال، با ما در میان بگذارید.