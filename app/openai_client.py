# app/openai_client.py

import os
import openai
from dotenv import load_dotenv

# Load environment variables
dotenv_path = next(
    p for p in (
        os.path.join(os.path.dirname(__file__), '..', '.env'),
        os.path.join(os.path.dirname(__file__), '.env')
    ) if os.path.exists(p)
)
load_dotenv(dotenv_path)

# Create OpenAI client
from openai import AsyncOpenAI

client = AsyncOpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL")
)

# Define prompt file paths
ROOT = os.path.join("knowledgebase")
NEW_USER_PROMPT_FILE = os.path.join(ROOT, "prompt_new_user.txt")
RETURNING_USER_PROMPT_FILE = os.path.join(ROOT, "prompt_returning_user.md")
GENERAL_PROMPT_FILE = os.path.join(ROOT, "general_amlak_promt.md")