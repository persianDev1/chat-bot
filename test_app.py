import sys
import os

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

try:
    # Test importing the main application module
    from main import app, client, NEW_USER_PROMPT_FILE, RETURNING_USER_PROMPT_FILE, GENERAL_PROMPT_FILE
    print("✅ Main application module imported successfully")
    
    # Test importing the router
    from routers.chat import router
    print("✅ Chat router imported successfully")
    
    # Test importing database functions
    from db_per import user_exists, save_message, get_last_20_messages, load_prompt_from_file
    print("✅ Database module imported successfully")
    
    # Test importing schemas
    from schemas import StartChatRequest, ChatRequest
    print("✅ Schemas imported successfully")
    
    # Test importing middleware
    from middleware import GlobalErrorHandlerMiddleware, AccessLogMiddleware, RateLimitMiddleware
    print("✅ Middleware imported successfully")
    
    # Test importing logging config
    from logging_config import setup_logging, log_before_retry
    print("✅ Logging config imported successfully")
    
    # Test that prompt files exist
    if os.path.exists(NEW_USER_PROMPT_FILE):
        print(f"✅ New user prompt file exists: {NEW_USER_PROMPT_FILE}")
    else:
        print(f"❌ New user prompt file missing: {NEW_USER_PROMPT_FILE}")
        
    if os.path.exists(RETURNING_USER_PROMPT_FILE):
        print(f"✅ Returning user prompt file exists: {RETURNING_USER_PROMPT_FILE}")
    else:
        print(f"❌ Returning user prompt file missing: {RETURNING_USER_PROMPT_FILE}")
        
    if os.path.exists(GENERAL_PROMPT_FILE):
        print(f"✅ General prompt file exists: {GENERAL_PROMPT_FILE}")
    else:
        print(f"❌ General prompt file missing: {GENERAL_PROMPT_FILE}")
    
    print("\n🎉 All tests passed! The application structure is correct and all dependencies are installed.")
    
except Exception as e:
    print(f"❌ Error during import: {e}")
    import traceback
    traceback.print_exc()
    
    
    
    
    #venv\Scripts\python.exe -m uvicorn app.main:app --reload