# --- memory_manager.py ---

import os
import asyncio
from mem0 import Memory
from config import logger

class MemoryManager:
    def __init__(self):
        # 配置 Mem0 使用本地的 ChromaDB 存储长期记忆，不需要额外服务器
        config = {
            "vector_store": {
                "provider": "chroma",
                "config": {
                    "collection_name": "agent_long_term_memory",
                    "path": "./memory_db"  # 数据库文件会保存在项目这个目录下
                }
            }
        }
        self.memory = Memory.from_config(config)
        # 长期记忆是跨越会话的（Cross-session），所以我们需要一个固定的用户 ID
        # 对于个人助理，写死一个默认的 user_id 即可
        self.user_id = "master_user" 

    def save_facts(self, text: str):
        """
        写入记忆：将大段文本喂给 Mem0，它会自动提取关键事实（如偏好、人物、事件），
        并自动处理历史记忆的合并与覆盖。
        """
        try:
            # Mem0 内部是同步调用 OpenAI 的，所以可能耗时，我们稍后用 to_thread 包裹
            self.memory.add(text, user_id=self.user_id)
            logger.info("🧠 [长期记忆] 背景资料已成功提取并沉淀至向量图谱中。")
        except Exception as e:
            logger.error(f"长期记忆写入失败: {e}")

    def retrieve(self, query: str, limit: int = 3) -> str:
        """
        检索记忆：根据当前的对话语义，去向量库里捞出最相关的 3 条记忆（RAG）。
        """
        try:
            results = self.memory.search(query, user_id=self.user_id, limit=limit)
            if not results:
                return ""
            
            # Mem0 返回的数据结构包含了提取出的 memory 文本
            memories = [res["memory"] for res in results]
            return "\n".join([f"- {m}" for m in memories])
        except Exception as e:
            logger.error(f"长期记忆检索失败: {e}")
            return ""

# 实例化全局单例
long_term_memory = MemoryManager()