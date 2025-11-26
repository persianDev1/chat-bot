# app/routers/chat.py ────────────────────────────────────────────────────────

import json
import asyncio
import logging
import os
from typing import AsyncIterator, List, Dict, Any

# کتابخانه‌های FastAPI
from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import StreamingResponse

# کتابخانه Tenacity برای مدیریت تلاش مجدد
from tenacity import retry, retry_if_exception_type, wait_exponential, stop_after_attempt

# کتابخانه‌های OpenAI
from openai import APITimeoutError, APIConnectionError, RateLimitError, APIError

# ماژول‌های داخلی پروژه
from ..schemas import StartChatRequest, ChatRequest
from ..db_per import user_exists, save_message, get_last_20_messages, load_prompt_from_file
from ..logging_config import log_before_retry
from ..openai_client import client, NEW_USER_PROMPT_FILE, RETURNING_USER_PROMPT_FILE, GENERAL_PROMPT_FILE

# سرویس‌ها و ابزارهای جدید
from ..services import CategoryManager
from ..tools import TOOLS_SCHEMA, handle_search_booths

# --------------------------------------------------------------------------- #
# تنظیمات اولیه و لاگرها
# --------------------------------------------------------------------------- #

app_logger = logging.getLogger("app." + __name__)
openai_logger = logging.getLogger("openai." + __name__)

router = APIRouter()
MODEL_NAME = os.getenv("OPENAI_MODEL_NAME", "gpt-4o-mini")

# لیست خطاهایی که ارزش تلاش مجدد دارند (Recoverable Errors)
RECOVERABLE = (APITimeoutError, APIConnectionError, RateLimitError, APIError)


# --------------------------------------------------------------------------- #
# توابع کمکی (Helper Functions)
# --------------------------------------------------------------------------- #

@retry(
    retry=retry_if_exception_type(RECOVERABLE),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    stop=stop_after_attempt(3),
    reraise=True,
    before_sleep=log_before_retry
)
async def _stream_completion(messages: List[Dict], tools: List[Dict] = None):
    """
    ارسال درخواست به OpenAI API با قابلیت Retry و پشتیبانی از ابزارها.
    
    Args:
        messages: لیست تاریخچه پیام‌ها.
        tools: لیست ابزارهای قابل استفاده (اختیاری).
    """
    return await client.chat.completions.create(
        model=MODEL_NAME,
        messages=messages,
        temperature=0.5,
        stream=True,
        timeout=25,  # تایم‌اوت افزایش یافته تا زمان کافی برای پردازش ابزار باشد
        tools=tools
    )

def sse_event(data: dict) -> str:
    """فرمت‌دهی داده‌ها برای ارسال به صورت Server-Sent Events (SSE)."""
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


# --------------------------------------------------------------------------- #
# اندپوینت شروع گفتگو (Start Chat) - 
# --------------------------------------------------------------------------- #

@router.post("/start_chat")
async def start_chat(req: StartChatRequest, bg: BackgroundTasks):
    """این اندپوینت سشن جدید می‌سازد و پیام خوش‌آمدگویی می‌فرستد."""
    cid = req.phone_number
    app_logger.info(f"New request received for /start_chat for user {cid}.")

    # --- سناریوی کاربر جدید ---
    if not await user_exists(cid):
        welcome_txt = load_prompt_from_file(NEW_USER_PROMPT_FILE) or "Hello! Welcome to the smart real estate assistant."
        
        async def gen_new() -> AsyncIterator[str]:
            yield sse_event({"conversation_id": cid, "message": ""}) # Heartbeat
            await asyncio.sleep(0.1)
            yield sse_event({"conversation_id": cid, "message": welcome_txt})
            yield "data: [DONE]\n\n"
            bg.add_task(save_message, cid, "assistant", welcome_txt)

        return StreamingResponse(gen_new(), media_type="text/event-stream")
    
    # --- سناریوی کاربر بازگشتی ---
    else:
        history = await get_last_20_messages(cid)
        system_content = (
            f"{load_prompt_from_file(GENERAL_PROMPT_FILE)}\n\n"
            f"{load_prompt_from_file(RETURNING_USER_PROMPT_FILE)}"
        )
        messages = [{"role": "system", "content": system_content}] + history

        async def gen_returning() -> AsyncIterator[str]:
            full_resp = ""
            try:
                openai_logger.debug(f"Sending {len(messages)} messages to OpenAI for user {cid}.")
                stream = await _stream_completion(messages)
                
                async for chunk in stream:
                    choices = getattr(chunk, "choices", None)
                    if not choices: continue
                    
                    delta = getattr(choices[0], "delta", None)
                    if not delta: continue
                    
                    content = getattr(delta, "content", "")
                    if content:
                        full_resp += content
                        yield sse_event({"conversation_id": cid, "message": content})
                   
                yield "data: [DONE]\n\n"
                bg.add_task(save_message, cid, "assistant", full_resp)

            except RECOVERABLE:
                openai_logger.error("Recoverable error during stream in /start_chat", exc_info=True)
                msg = "We are currently unable to respond; please try again later."
                yield sse_event({"conversation_id": cid, "message": msg})
                yield "data: [DONE]\n\n"
            except Exception:
                openai_logger.error("Unexpected error in /start_chat stream", exc_info=True)
                msg = "An error occurred while processing the stream."
                yield sse_event({"conversation_id": cid, "message": msg})
                yield "data: [DONE]\n\n"

        return StreamingResponse(gen_returning(), media_type="text/event-stream")


# --------------------------------------------------------------------------- #
# اندپوینت ادامه گفتگو (Chat) - با قابلیت هوشمند ابزار
# --------------------------------------------------------------------------- #

@router.post("/chat")
async def handle_chat(req: ChatRequest, bg: BackgroundTasks):
    """
    مدیریت پیام‌های کاربر با قابلیت فراخوانی ابزار (Function Calling).
    """
    cid, user_msg = req.conversation_id, req.message
    # دریافت مختصات جغرافیایی کاربر (اگر فرانت‌‌اند ارسال کرده باشد)
    user_lat, user_lon = req.latitude, req.longitude
    
    app_logger.info(f"Chat Request: {cid} | Coords: {user_lat}, {user_lon}")
    
    # ۱. ساخت سیستم پرامپت داینامیک
    # لیست دسته‌بندی‌های فعال را از سرویس می‌گیریم و به پرامپت تزریق می‌کنیم
    base_prompt = load_prompt_from_file(GENERAL_PROMPT_FILE)
    categories_list = CategoryManager.get_prompt_text()
    
    # -----------------------------------------------------------------------
    # ساخت کانتکست مربوط به موقعیت مکانی (Location Context)
    # -----------------------------------------------------------------------
    if user_lat and user_lon:
        location_info = (
            "✅ [LOCATION STATUS]: GPS Location IS provided by the user. "
            "You do NOT need to ask for the city name. "
            "If the user asks for services 'here' or 'nearby', simply call the tool with city_name=null."
        )
    else:
        location_info = (
            "❌ [LOCATION STATUS]: GPS Location is NOT provided. "
            "If the user asks for a service but has not mentioned a city name, "
            "you MUST ask them for their city first before searching."
        )

    # -----------------------------------------------------------------------
    # ترکیب نهایی سیستم پرامپت
    # -----------------------------------------------------------------------
    system_content = (
        f"{base_prompt}\n\n"
        f"{location_info}\n\n"  # ✅ اینجا وضعیت لوکیشن دقیق مشخص شد
        f"--- ACTIVE BUSINESS CATEGORIES (ID: Name) ---\n"
        f"Use ONLY these IDs for the 'search_booths' tool:\n"
        f"{categories_list}\n"
        f"---------------------------------------------"
    )
    
    # ۲. آماده‌سازی تاریخچه پیام‌ها
    history = await get_last_20_messages(cid)
    messages = [{"role": "system", "content": system_content}] + history
    messages.append({"role": "user", "content": user_msg})

    # ۳. تعریف تولیدکننده استریم (Generator Logic)
    async def generate_chat_stream() -> AsyncIterator[str]:
        nonlocal messages # دسترسی به متغیر messages برای آپدیت تاریخچه در طول مکالمه
        full_resp = ""
        
        # لیست موقت برای جمع‌آوری تکه‌های ابزار (Tool Call Chunks)
        tool_calls_buffer: List[Dict[str, Any]] = []
        
        try:
            # بلافاصله پیام کاربر را در پس‌زمینه ذخیره می‌کنیم
            bg.add_task(save_message, cid, "user", user_msg)
            
            # --- فاز ۱: ارسال پیام به OpenAI (با معرفی ابزارها) ---
            openai_logger.debug(f"Phase 1: Sending request to OpenAI for user {cid}")
            stream1 = await _stream_completion(messages, tools=TOOLS_SCHEMA)
            
            async for chunk in stream1:
                if not chunk.choices: continue
                delta = chunk.choices[0].delta
                
                # حالت A: مدل متن معمولی تولید می‌کند
                if delta.content:
                    full_resp += delta.content
                    yield sse_event({"conversation_id": cid, "message": delta.content})
                
                # حالت B: مدل دستور اجرای ابزار صادر می‌کند (تکه تکه)
                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        idx = tc.index
                        
                        # اطمینان از وجود جایگاه در بافر
                        while len(tool_calls_buffer) <= idx:
                            tool_calls_buffer.append({
                                "id": "",
                                "type": "function",
                                "function": {"name": "", "arguments": ""}
                            })
                        
                        # پر کردن اطلاعات ابزار
                        if tc.id:
                            tool_calls_buffer[idx]["id"] = tc.id
                        if tc.function:
                            if tc.function.name:
                                tool_calls_buffer[idx]["function"]["name"] += tc.function.name
                            if tc.function.arguments:
                                tool_calls_buffer[idx]["function"]["arguments"] += tc.function.arguments

            # --- فاز ۲: بررسی و اجرای ابزارها ---
            
            # فقط ابزارهایی که ID معتبر دارند را نگه می‌داریم
            valid_tools = [t for t in tool_calls_buffer if t["id"]]
            
            if valid_tools:
                # الف) درخواست ابزار را به تاریخچه اضافه می‌کنیم
                messages.append({
                    "role": "assistant",
                    "content": None,
                    "tool_calls": valid_tools
                })
                
                # ب) اجرای تک تک ابزارها
                for tc in valid_tools:
                    fn_name = tc["function"]["name"]
                    fn_args_str = tc["function"]["arguments"]
                    
                    # تبدیل JSON آرگومان‌ها به دیکشنری
                    try:
                        fn_args = json.loads(fn_args_str)
                    except json.JSONDecodeError:
                        app_logger.error(f"JSON Decode Error: {fn_args_str}")
                        fn_args = {}

                    app_logger.info(f"🛠️ Executing Tool: {fn_name} | Args: {fn_args}")
                    
                    tool_result_content = ""
                    
                    if fn_name == "search_booths":
                        # فراخوانی تابع پایتونی (با تزریق وابستگی‌ها)
                        tool_result_content = await handle_search_booths(
                            category_id=fn_args.get("category_id"),
                            city_name=fn_args.get("city_name"),
                            user_lat=user_lat, # مختصات از ریکوئست اصلی
                            user_lon=user_lon
                        )
                    else:
                        tool_result_content = json.dumps({"error": f"Unknown tool: {fn_name}"})
                    
                    # ج) نتیجه ابزار را به تاریخچه اضافه می‌کنیم
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": tool_result_content
                    })

                # --- فاز ۳: دریافت پاسخ نهایی از مدل (با توجه به نتایج ابزار) ---
                openai_logger.debug("Phase 2: Sending tool outputs back to OpenAI")
                
                # این بار بدون tools درخواست می‌زنیم تا مدل فقط متن تولید کند
                stream2 = await _stream_completion(messages, tools=None)
                
                async for chunk in stream2:
                    delta = chunk.choices[0].delta if chunk.choices else None
                    if delta and delta.content:
                        full_resp += delta.content
                        yield sse_event({"conversation_id": cid, "message": delta.content})
            
            # پایان استریم
            yield "data: [DONE]\n\n"
            
            # ذخیره پاسخ نهایی مدل در دیتابیس (اگر متنی تولید شده باشد)
            if full_resp:
                bg.add_task(save_message, cid, "assistant", full_resp)

        except RECOVERABLE as e:
            # خطاهای قابل بازیابی (مثل قطعی موقت اینترنت)
            app_logger.warning(f"Recoverable Error in /chat: {e}")
            msg = "متاسفانه ارتباط با سرور قطع شد. لطفاً دوباره تلاش کنید."
            yield sse_event({"conversation_id": cid, "message": msg})
            yield "data: [DONE]\n\n"
            
        except Exception as e:
            # خطاهای غیرمنتظره سیستمی
            app_logger.error("Unexpected Error in /chat stream", exc_info=True)
            msg = "خطای سیستمی رخ داد. لطفاً با پشتیبانی تماس بگیرید."
            yield sse_event({"conversation_id": cid, "message": msg})
            yield "data: [DONE]\n\n"

    return StreamingResponse(generate_chat_stream(), media_type="text/event-stream")