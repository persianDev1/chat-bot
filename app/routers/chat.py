# app/routers/chat.py

import json
import asyncio
import logging
from typing import AsyncIterator

from httpx import stream

# Import project modules with relative paths
from ..schemas import StartChatRequest, ChatRequest
from ..db_per import user_exists, save_message, get_last_20_messages, load_prompt_from_file
from ..logging_config import log_before_retry

# Import client and variables from openai_client module
from ..openai_client import client, NEW_USER_PROMPT_FILE, RETURNING_USER_PROMPT_FILE, GENERAL_PROMPT_FILE

# Import from fastapi
from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import StreamingResponse

# Import from tenacity
from tenacity import retry, retry_if_exception_type, wait_exponential, stop_after_attempt

# Import from openai
from openai import APITimeoutError, APIConnectionError, RateLimitError, APIError

# Create loggers
app_logger = logging.getLogger("app." + __name__)
openai_logger = logging.getLogger("openai." + __name__)

# Create a new router
router = APIRouter()

# --- Helper functions ---
RECOVERABLE = (APITimeoutError, APIConnectionError, RateLimitError, APIError)

@retry(
    retry=retry_if_exception_type(RECOVERABLE),
    wait=wait_exponential(multiplier=1, min=2, max=8),
    stop=stop_after_attempt(3),
    reraise=True,
    before_sleep=log_before_retry
)
async def _stream_completion(messages):
    return await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        temperature=0.5,
        stream=True,
        timeout=15
    )

def sse_event(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

# --- Endpoints ---
# Note that @app.post has been changed to @router.post

@router.post("/start_chat")
async def start_chat(req: StartChatRequest, bg: BackgroundTasks):
    """This endpoint starts a new chat session"""
    cid = req.phone_number
    app_logger.info(f"New request received for /start_chat for user {cid}.")

    # --- Logical path for new user ---
    if not await user_exists(cid):
        welcome_txt = load_prompt_from_file(NEW_USER_PROMPT_FILE) or "Hello! Welcome to the smart real estate assistant."
        
        async def gen_new() -> AsyncIterator[str]:
            # Send an initial empty message (Heart-beat) to prevent browser timeout
            yield sse_event({"conversation_id": cid, "message": ""})
            await asyncio.sleep(0.1) # Small delay to ensure
            
            # Send the main welcome message
            yield sse_event({"conversation_id": cid, "message": welcome_txt})
            
            # Send stream end signal
            yield "data: [DONE]\n\n"
            
            # Save message to database in background
            bg.add_task(save_message, cid, "assistant", welcome_txt)

        return StreamingResponse(gen_new(), media_type="text/event-stream")
    else:
    # --- Logical path for returning user ---
    
        history = await get_last_20_messages(cid)
        system_content = (
            f"{load_prompt_from_file(GENERAL_PROMPT_FILE)}\n\n"
            f"{load_prompt_from_file(RETURNING_USER_PROMPT_FILE)}"
        )
        messages = [{"role": "system", "content": system_content}] + history

        async def gen_returning() -> AsyncIterator[str]:
            full_resp = ""
            try:
                # Loop through OpenAI response stream
                openai_logger.debug(f"Sending {len(messages)} messages to OpenAI for user {cid}.")
                stream = _stream_completion(messages)
                async for chunk in stream:
                    # If choices don't exist or are empty, skip this chunk
                    choices = getattr(chunk, "choices", None)
                    if not choices:
                        continue
                    choice = choices[0]
                    
                    finish_reason = getattr(choice, "finish_reason", None)
                    if finish_reason is not None:
                        openai_logger.warning(f"finish_reason received: {finish_reason}")
                        break
                    
                    # If delta doesn't exist or is empty, skip this chunk
                    delta = getattr(choices[0], "delta", None)
                    if not delta:
                        continue
                    # If content doesn't exist or is empty, skip this chunk
                    content = getattr(delta, "content", "")
                    if content:
                        full_resp += content
                        yield sse_event({"conversation_id": cid, "message": content})
                   

                yield "data: [DONE]\n\n"
                # After successful stream completion, save the full response in background
                bg.add_task(save_message, cid, "assistant", full_resp)

            except RECOVERABLE as e:
                # If after several attempts error still exists, show appropriate message to user
                openai_logger.error("Recoverable error during stream in /start_chat", exc_info=True)
                msg = "We are currently unable to respond; please try again later."
                yield sse_event({"conversation_id": cid, "message": msg})
                yield "data: [DONE]\n\n"
            except Exception as e:
                openai_logger.error("Unexpected error in /start_chat stream", exc_info=True)
                msg = "An error occurred while processing the stream."
                yield sse_event({"conversation_id": cid, "message": msg})
                yield "data: [DONE]\n\n"

        return StreamingResponse(gen_returning(), media_type="text/event-stream")

   

@router.post("/chat")
async def handle_chat(req: ChatRequest, bg: BackgroundTasks):
    """This endpoint handles subsequent messages in an existing conversation"""
    cid, user_msg = req.conversation_id, req.message
    app_logger.info(f"New request received for /chat for user {cid}.")
    
    # Get conversation history and prepare message list
    history = await get_last_20_messages(cid)
    sys_prompt = load_prompt_from_file(GENERAL_PROMPT_FILE)
    messages = [{"role": "system", "content": sys_prompt}] + history
    # Add new user message to the end of the list
    messages.append({"role": "user", "content": user_msg})

    # Define generator for streaming response
    async def generate_chat_stream() -> AsyncIterator[str]:
        full_resp = ""
        try:
            # User message is immediately queued for background saving
            bg.add_task(save_message, cid, "user", user_msg)
            
            # Loop through OpenAI response stream
            openai_logger.debug(f"Sending {len(messages)} messages to OpenAI for user {cid}.")
            stream = _stream_completion(messages)
            async for chunk in stream:
                 # If choices don't exist or are empty, skip this chunk
                choices = getattr(chunk, "choices", None)
                if not choices:
                     continue
                choice = choices[0]
                finish_reason = getattr(choice, "finish_reason", None)
                if finish_reason is not None:
                    openai_logger.warning(f"finish_reason received: {finish_reason}")
                    break
                delta = getattr(choices[0], "delta", None)
                if not delta:
                    continue
                content = getattr(delta, "content", "")
                if content:
                    full_resp += content
                    yield sse_event({"conversation_id": cid, "message": content})
            
            yield "data: [DONE]\n\n"
            # After stream completion, save assistant's full response in background
            bg.add_task(save_message, cid, "assistant", full_resp)

        except RECOVERABLE as e:
            # Handle recoverable errors
            openai_logger.error("Recoverable error during stream in /chat", exc_info=True)
            msg = "We are currently unable to respond; please try again later."
            yield sse_event({"conversation_id": cid, "message": msg})
            yield "data: [DONE]\n\n"
        except Exception as e:
            openai_logger.error("Unexpected error in /chat stream", exc_info=True)
            msg = "An error occurred while processing the stream."
            yield sse_event({"conversation_id": cid, "message": msg})
            yield "data: [DONE]\n\n"

    return StreamingResponse(generate_chat_stream(), media_type="text/event-stream")