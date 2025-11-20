# Correct code should start with this line
import openai  
import os
from dotenv import load_dotenv
from pathlib import Path
from openai import OpenAI

# Load variables from .env file
print("Loading variables from .env file...")
load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")
base_url = os.getenv("OPENAI_BASE_URL")

# Check if variables exist
if not api_key or not base_url:
    print("🔴 Error: Please ensure OPENAI_API_KEY and OPENAI_BASE_URL exist in your .env file.")
    exit()

print(f"Testing with Base URL: {base_url}")
print("-" * 30)

try:
    # Create client with your credentials
    client = openai.OpenAI(
        api_key=api_key,
        base_url=base_url,
    )

    print("✅ OpenAI client created successfully.")
    
    # Test 1: Check access to models
    # print("\n🔍 Test 1: Checking list of available models...")
    # try:
    #     models = client.models.list()
    #     print(f"✅ Number of available models: {len(models.data)}")
        
    #     # Display ALL models (not just the first 3)
    #     if models.data:
    #         print("🎯 All available models:")
    #         for i, model in enumerate(models.data):
    #             print(f"   {i+1}. {model.id}")
    #             # Show additional model details if available
    #             if hasattr(model, 'created'):
    #                 print(f"      Created: {model.created}")
    #             if hasattr(model, 'owned_by'):
    #                 print(f"      Owned by: {model.owned_by}")
    #             print()  # Add space between models
    #     else:
    #         print("⚠️  No models found in the list.")
            
    # except Exception as e:
    #     print(f"❌ Error retrieving model list: {e}")

    # Test 2: Simple Chat Completion request
    print("\n🔍 Test 2: Sending a Chat Completion request...")
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",  # or any other model available in your service
            messages=[
                {"role": "system", "content": """
                 شما یک متخصص زبان فارسی هستید که در تبدیل کلمات فارسی به نگارش فونتیک برای تلفظ صحیح مهارت دارید. لطفاً کلمه یا عبارت زیر را به صورت فونتیک فارسی بنویسید تا موتور تبدیل متن به گفتار (TTS) بتواند آن را با تلفظ صحیح بخواند. از علامت‌های فتحه (َ)، کسره (ِ)، ضمه (ُ)، تشدید (ّ) و سایر نشانه‌های لازم برای نشان دادن تلفظ دقیق استفاده کنید. کلمه یا عبارت: "رهن" 
خروجی فقط باید نگارش فونتیک باشد، بدون توضیح اضافی..
"""},

                {"role": "user", "content": "سلام کلمه رهن رو به صورت فونتیک بنویسید"""}
            ],
            max_tokens=50,
            temperature=0.7
        )
        
        assistant_reply = response.choices[0].message.content
        print(f"✅ Response received: {assistant_reply}")
        print(f"📊 Token usage: {response.usage.total_tokens} (input: {response.usage.prompt_tokens}, output: {response.usage.completion_tokens})")
        
    except Exception as e:
        print(f"❌ Error in Chat Completion: {e}")

    # Test 3: Check Assistants API (optional)
    print("\n🔍 Test 3: Checking access to Assistants API...")
    try:
        assistants = client.beta.assistants.list(limit=1)
        print("✅ Assistants API is available.")
        print("🎯 You can use Assistants, Threads, and Runs features.")
        
    except openai.NotFoundError:
        print("⚠️  Assistants API not found (404 error).")
        print("   Most likely, your service provider doesn't support this feature yet.")
        
    except Exception as e:
        print(f"❌ Error in Assistants API: {e}")

    print("\n" + "="*50)
    print("🎉 Main tests completed!")
    print("✅ Your API Key and Base URL are working correctly.")

except openai.AuthenticationError:
    print("\n❌ Failure: Authentication error.")
    print("Please make sure your API key (OPENAI_API_KEY) is correct.")

except openai.APIConnectionError:
    print(f"\n❌ Failure: Cannot establish connection to {base_url}.")
    print("Please check your Base URL and internet connection.")

except openai.APIError as e:
    print(f"\n❌ Failure: An API error occurred.")
    print(f"Error details: {e}")

except Exception as e:
    print(f"\n🔴 Unexpected error: {e}")
    print("Please check your settings.")

print("\n" + "-"*30)
print("Test completed.")

# client = openai.OpenAI(
#     api_key=api_key,
#     base_url=base_url,
# )






    # Test 4: Text-to-Speech test
# print("\n🔍 Test 4: Testing Text-to-Speech...")
# response = client.audio.speech.create(
#             model="gpt-4o-mini-tts",
#             voice="alloy",
#             input="""   
#             سلام و خوش آمدید به سامانه خدمات املاک ملل آسیا! 🎉😊  
# ما اینجا هستیم تا با **مشاوره تخصصی** و **پشتیبانی ۲۴ ساعته**، فرآیند **خرید/فروش**، **رهن/اجاره** و **سرمایه‌گذاری** در املاک را برای شما ساده، شفاف و لذت‌بخش کنیم.

# در سایت ما بخش‌های زیر را خواهید دید:  
# • صفحه اصلی – معرفی خدمات و ویژگی‌ها  
# • خرید و فروش – ثبت درخواست خرید یا فروش ملک  
# • رهن و اجاره – ثبت درخواست رهن یا اجاره  
# • سرمایه‌گذاری – آغاز طرح‌های سرمایه‌ای با بازده بالا  
# • ثبت‌نام/ورود – احراز هویت با شماره موبایل و کد پیامکی  
# • پنل کاربری – مشاهده و پیگیری درخواست‌ها   

# مراحل استفاده بسیار آسان است:  
# 1️⃣ **ثبت‌نام/ورود** با شماره موبایل  
# 2️⃣ **انتخاب خدمت** (خرید/فروش، رهن/اجاره یا سرمایه‌گذاری)  
# 3️⃣ **تکمیل فرم آنلاین** مرتبط با خدمت انتخابی  
# 4️⃣ **پیگیری و مدیریت** درخواست در پنل کاربری  
# 5️⃣ **پشتیبانی** تا عقد قرارداد و تحویل نهایی  

# اگر در مسیر هر مرحله سؤالی داشتید، با کمال میل در خدمتیم! 🌟🏡✨
            
#             """
#         )
        
# with open("output3.mp3", "wb") as f:
#             f.write(response.content)
        
        
        
   