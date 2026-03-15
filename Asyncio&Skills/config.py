import os
import logging
from langfuse.openai import AsyncOpenAI
from tavily import TavilyClient
from dotenv import load_dotenv


load_dotenv()


logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[logging.StreamHandler() ]
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger("AgentEngine")


class Config:
    API_KEY = os.getenv("OPENAI_API_KEY")
    BASE_URL = os.getenv("OPENAI_BASE_URL") 
    MODEL = os.getenv("MODEL_NAME")
    DB_PATH = "agent_memory.db"  
    TOKEN_SOFT_LIMIT = 10000      
    TOKEN_ENCODING = "cl100k_base"
    SUMMARY_MODEL = os.getenv("MODEL_NAME") 


    @classmethod
    def validate(cls):
        if not cls.API_KEY:
            raise ValueError("错误: 未在 .env 中找到 OPENAI_API_KEY。")


Config.validate()

# Langfuse 会自动读取环境变量中的 LANGFUSE 密钥，如果没有配置，它会静默降级为普通请求
client = AsyncOpenAI(api_key=Config.API_KEY, base_url=Config.BASE_URL)
tavily = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))