# --- memory_manager.py ---
import os
import uuid
import chromadb
from chromadb.api.types import EmbeddingFunction, Documents, Embeddings
from config import logger
from dotenv import load_dotenv
import openai


load_dotenv()


# 配置自定义 Embedding 函数，对接 API
# 这里模拟一个符合 ChromaDB 标准的 Embedding 函数
class CustomEmbeddingFunction(EmbeddingFunction):
    def __call__(self, input: Documents) -> Embeddings:
        # 这里直接使用在 .env 中定义的 EBD 系列环境变量
        client = openai.OpenAI(
            api_key=os.getenv("EBD_API_KEY"),
            base_url=os.getenv("EBD_BASE_URL")
        )

        # 服务商限制：单次 API 请求最多 32 个文本块
        MAX_BATCH_SIZE = 32
        all_embeddings = []

        # 核心修复：把大数组切分成多个最多 32 长度的小批次，循环发送
        for i in range(0, len(input), MAX_BATCH_SIZE):
            batch_input = input[i : i + MAX_BATCH_SIZE]
            
            try:
                response = client.embeddings.create(
                    input=batch_input,
                    model=os.getenv("EBD_MODEL_NAME")
                )
                # 将这一批次的向量结果追加到总列表中
                all_embeddings.extend([d.embedding for d in response.data])
            except Exception as e:
                logger.error(f"Embedding API 第 {i} 批次请求失败: {e}")
                # 生产环境建议抛出异常或重试，这里直接抛出让上层捕获
                raise e 
                
        return all_embeddings


class MemoryManager:
    def __init__(self):
        # 初始化 ChromaDB 持久化存储
        self.client = chromadb.PersistentClient(path="./memory_db")
        
        # 创建 Collection，传入自定义的 Embedding 函数，ChromaDB 会自动识别 __call__
        self.collection = self.client.get_or_create_collection(
            name="agent_long_term_memory",
            embedding_function=CustomEmbeddingFunction()
        )
        self.user_id = "master_user"

    def save_facts(self, text: str):
        """将事实存入 ChromaDB (附带防 512 Token 超限的截断分块功能)"""
        # 简单暴力的切分逻辑：假设 1 Token ≈ 1.5 到 2 个中文字符
        # 这里设置为每 2000 个字符切一块，绝对安全不会触发 512 Token 报错
        chunk_size = 2000
        chunks = [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]
        
        if not chunks: return

        try:
            # 批处理性能优化
            # 一次性生成所有的 ID 和 Metadata
            mem_ids = [str(uuid.uuid4()) for _ in chunks]
            metadatas = [{"user_id": self.user_id} for _ in chunks]

            # 把数组直接传给 ChromaDB！底层 Embedding 函数会把整个数组一次性发给 API
            self.collection.add(
                documents=chunks,
                metadatas=metadatas,
                ids=mem_ids
            )
            logger.info(f"🧠 [长期记忆] 事实已分成 {len(chunks)} 个碎片，沉淀至向量库。")
        except Exception as e:
            logger.error(f"长期记忆写入失败: {e}")

    def retrieve(self, query: str, limit: int = 3, threshold: float = 1.3) -> str:
        """检索：带有严格阈值过滤的高级捞取"""
        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=limit,
                where={"user_id": self.user_id} # 物理隔离：只捞当前用户的数据
            )
            docs = results.get('documents', [[]])[0]
            distances = results.get('distances', [[]])[0]
            
            valid_docs = []

            # 核心控制逻辑：双重循环遍历对比
            for doc, distance in zip(docs, distances):
                # 因为 Chroma 默认用 L2 距离，所以距离越小越好，这里用 < 号
                # 如果你的 Chroma 配置成了 Cosine，这里就要改成 distance > threshold
                if distance < threshold:
                    valid_docs.append(doc)
                    logger.debug(f"放行: 距离 {distance:.4f} < 阈值 {threshold}")
                else:
                    logger.warning(f"拦截: 距离 {distance:.4f} >= 阈值 {threshold} (文本已被丢弃)")

            return "\n".join([f"- {doc}" for doc in valid_docs]) if valid_docs else ""
        except Exception as e:
            logger.error(f"长期记忆检索失败: {e}")
            return ""
    
# 实例化全局单例
long_term_memory = MemoryManager()