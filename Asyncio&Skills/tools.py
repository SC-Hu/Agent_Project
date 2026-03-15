import os
import json
import inspect
from config import tavily


# --- 技能包元数据（描述各领域的作用，专门喂给 Router 看的） ---
CATEGORY_METADATA = {
    "office": "涉及读取/写入本地文件、代码文档、收发邮件、办公自动化操作。",
    "gamedev": "涉及游戏开发、引擎崩溃报错日志分析、剧情对话树生成、游戏数值平衡。"
    # base 技能（搜索和提交）是底层被动技能，不需要让 Router 知道，直接默认加载
}


# --- 将原本单一的字典，升级为分类存储的技能注册表 ---
SKILL_REGISTRY = {
    "base": {"tools": {}, "schemas": []},
    "office": {"tools": {}, "schemas":[]},
    "gamedev": {"tools": {}, "schemas":[]}
}

def register_tool(category="base"):
    """
    带分类的工具注册装饰器
    """
    def decorator(func):
        sig = inspect.signature(func)
        doc = inspect.getdoc(func) or ""
        properties = {}
        required =[]
    
        for name, param in sig.parameters.items():
            # 将 Python 类型映射为 JSON Schema 类型
            param_type = "string"
            if param.annotation == int: param_type = "integer"
            elif param.annotation == float: param_type = "number"
            elif param.annotation == bool: param_type = "boolean"
            elif param.annotation == list: param_type = "array"
            elif param.annotation == dict: param_type = "object"
            
            properties[name] = {
                "type": param_type,
                "description": f"参数 {name}" # 简易处理：如有需要，可通过正则从 doc 中提取更详细的参数说明
            }
            
            # 如果没有默认值，则为必填项
            if param.default == inspect.Parameter.empty:
                required.append(name)
                
        schema = {
            "type": "function",
            "function": {
                "name": func.__name__,
                "description": doc.strip().replace("\n", " "), # 将多行注释压缩
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required
                }
            }
        }
        
        # 将工具存入对应的分类抽屉中
        if category not in SKILL_REGISTRY:
            SKILL_REGISTRY[category] = {"tools": {}, "schemas": []}
        
        SKILL_REGISTRY[category]["tools"][func.__name__] = func
        SKILL_REGISTRY[category]["schemas"].append(schema)
        return func
    return decorator


# Base Skill

@register_tool(category="base")
def google_search(query: str) -> str:
    """
    当用户询问实时信息、新闻、历史事实、特定人物或需要查阅互联网资料时使用。
    必须遵循'全要素'原则，输入具体的搜索查询语句（例如：'特斯拉(Tesla)最新股价行情'）。
    """
    try:
        response = tavily.search(query=query, search_depth="advanced", max_results=3)
        results =[f"来源: {r['url']}\n内容: {r['content']}" for r in response['results']]
        return "\n\n".join(results) if results else "未找到相关搜索结果。"
    except Exception as e:
        return f"搜索过程中发生错误: {str(e)}"

# 大模型使用的“提交答案”工具
@register_tool(category="base")
def submit_final_answer(answer: str) -> str:
    """
    当且仅当你确信已经完美解决用户问题时，调用此工具将最终答案提交给用户。
    注意：排版要精美，使用 Markdown 格式。
    """
    # 这个函数本身不需要真实执行逻辑，它的参数会被 engine.py 拦截并触发 Reflection
    return "已提交审核"


# Office Skill

@register_tool(category="office")
async def read_local_file(file_path: str) -> str:
    """读取本地计算机上的文本文件（如 .txt, .md, .py）。传入绝对或相对路径。"""
    try:
        if not os.path.exists(file_path):
            return f"错误：文件 {file_path} 不存在。"
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        # 防止文件过大撑爆上下文，截断前 10000 个字符
        return content[:10000] + ("\n...(已截断)" if len(content) > 10000 else "")
    except Exception as e:
        return f"读取文件失败: {e}"

@register_tool(category="office")
async def write_local_file(file_path: str, content: str) -> str:
    """将内容写入或覆盖到本地文件中。如果文件不存在会自动创建。"""
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return f"成功！内容已保存至 {file_path}"
    except Exception as e:
        return f"写入文件失败: {e}"

@register_tool(category="office")
async def send_mock_email(to_address: str, subject: str, body: str) -> str:
    """发送工作邮件给指定联系人。"""
    # 这里我们用 mock 模拟，如果你有真实 SMTP 需求可以替换
    return f"【邮件发送成功】收件人: {to_address} | 主题: {subject}\n系统提示：已成功投递。"


# GameDev Skill

@register_tool(category="gamedev")
async def analyze_engine_log(log_snippet: str) -> str:
    """
    当 Unity 或 Unreal 引擎崩溃时，分析报错日志切片。
    输入一段 Exception 日志，返回可能导致崩溃的 C#/C++ 模块定位。
    """
    # 模拟日志分析逻辑
    if "NullReferenceException" in log_snippet:
        return "诊断结果：空引用异常。建议检查 Awake 或 Start 阶段的 GameObject 绑定是否丢失。"
    elif "Access Violation" in log_snippet:
        return "诊断结果：C++ 内存越界或野指针。请检查最近修改的 Unmanaged 内存分配逻辑。"
    return "诊断结果：未知报错。请尝试使用 google_search 工具查找该 Error Code。"

@register_tool(category="gamedev")
async def generate_dialogue_json(npc_name: str, topic: str) -> str:
    """
    根据剧情设定，为指定 NPC 生成合法的对话树结构（直接输出供引擎读取的 JSON 字符串格式）。
    """
    mock_tree = {
        "NPC": npc_name,
        "Nodes":[
            {"id": 1, "text": f"关于{topic}，其实我知道的不多...", "options":[
                {"choice": "继续追问", "next_node": 2},
                {"choice": "离开", "next_node": -1}
            ]}
        ]
    }
    return json.dumps(mock_tree, ensure_ascii=False, indent=2)