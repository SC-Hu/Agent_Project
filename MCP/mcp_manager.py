from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from tools import TOOLKIT_REGISTRY, TOOLKIT_METADATA
from config import logger, Config
import contextlib
import json
import os

class MCPManager:
    def __init__(self):
        # AsyncExitStack 保证整个 Agent 运行期间 MCP 服务一直运行
        # 使用 async with 在进程结束时，连接就断了
        self.exit_stack = contextlib.AsyncExitStack()
        self.sessions = {}  # {toolkit_name: session}

    async def connect_to_server(self, server_id: str, toolkit_name: str, command: str, args: list, env: dict = None):
        """
        server_id: 用于命名空间 (如 filesystem)
        toolkit_name: 用于注册表归类 (如 office)
        """
        logger.info(f"正在连接 MCP Server: {server_id}...")
        # 启动图纸，定义了要启动什么外部程序
        server_params = StdioServerParameters(
            command=command, 
            args=args,
            env=env
            )
        
        # 1. 建立 stdio 传输并进入 context
        # stdio_client 根据图纸执行进程
        # enter_async_context 将进程连接到 AsyncExitStack 上保证存活
        # read_stream, write_stream 是 读数据管, 写数据管
        read_stream, write_stream = await self.exit_stack.enter_async_context(stdio_client(server_params))
        
        # 2. 创建并初始化会话
        # ClientSession 建立标准 MCP 协议对话（JSON-RPC 格式）
        session = await self.exit_stack.enter_async_context(ClientSession(read_stream, write_stream))
        await session.initialize()
        
        self.sessions[server_id] = session
        
        # 3. 发现并注册工具
        tools_result = await session.list_tools()
        
        if toolkit_name not in TOOLKIT_REGISTRY:
            TOOLKIT_REGISTRY[toolkit_name] = {
                "description": TOOLKIT_METADATA.get(toolkit_name, ""),
                "tools": {},
                "schemas": []
            }

        for tool in tools_result.tools:
            # 命名空间优化：ID 格式 -> mcp_[Server名]_[工具名]
            # 这样即便两个 Server 都有 read_file，也不会冲突
            tool_id = f"mcp__{server_id}__{tool.name}"
            
            # --- 关键：定义代理执行函数 ---
            # 当 Agent 调用 mcp_xxx 时，实际上是把参数转发给 Node.js 进程
            async def mcp_proxy(t_name=tool.name, s_id=server_id, **kwargs):
                current_session = self.sessions.get(s_id)
                if not current_session:
                    return "错误：MCP 会话已断开。"
                
                # 向外部进程发起远程过程调用 (RPC)
                result = await current_session.call_tool(t_name, arguments=kwargs)
                
                # 核心优化，判断 MCP Server 是否返回了错误标识
                if getattr(result, 'isError', False):
                    error_msg = "\n".join([c.text for c in result.content if hasattr(c, 'text')])
                    return f"工具执行报错: {error_msg}"

                # 拼接返回结果
                output = []
                for content in result.content:
                    if hasattr(content, 'text'):
                        output.append(content.text)
                return "\n".join(output) if output else "执行成功，无返回文本"

            # --- 注册进系统，欺骗大模型 ---
            TOOLKIT_REGISTRY[toolkit_name]["tools"][tool_id] = {
                "func": mcp_proxy,
                "requires_approval": True, # 外部工具统一设为需审批，保证安全
                "description": tool.description
            }
            
            # 将 MCP 发来的标准 JSON Schema 转换成 OpenAI 格式
            # imputSchema 100% 兼容 OpenAI JSON Schema 格式
            TOOLKIT_REGISTRY[toolkit_name]["schemas"].append({
                "type": "function",
                "function": {
                    "name": tool_id,
                    "description": f"[MCP][{server_id}]{tool.description}",
                    "parameters": tool.inputSchema
                }
            })
            
        logger.info(f"✅ 成功加载 MCP 工具箱: {server_id} -> {toolkit_name}")

    async def close_all(self):
        """退出程序时关闭所有 Node.js 进程"""
        await self.exit_stack.aclose()
        logger.info("所有 MCP Server 进程已安全关闭。")

    async def load_config(self, config_path: str):
        """
        从配置文件自动扫描并连接所有 MCP Server
        """
        if not os.path.exists(config_path):
            logger.warning(f"未找到 MCP 配置文件: {config_path}")
            return
        
        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
            
        servers = config_data.get("mcpServers", {})
        for server_id, server_info in servers.items():
            try:
                command = server_info.get("command")
                args = server_info.get("args", [])
                target_toolkit = server_info.get("toolkit", "base") 
                
                # --- 路径占位符动态替换 ---
                # 将配置文件中的占位符替换为真实的 Config.WORKSPACE_ROOT
                processed_args = [
                    arg.replace("WORKSPACE_PLACEHOLDER", Config.WORKSPACE_ROOT) 
                    for arg in args
                ]

                # --- 环境变量占位符解析 ---
                raw_env = server_info.get("env", {})
                # 默认继承当前进程的环境变量（包含 .env 加载的内容）
                full_env = os.environ.copy()
                
                for key, value in raw_env.items():
                    # 如果 value 是一个已存在的环境变量名，则取环境变量的值
                    # 否则，直接使用 value 字符串本身（Claude标准做法）
                    env_value = os.getenv(value)
                    if env_value:
                        full_env[key] = env_value
                    else:
                        full_env[key] = value
                
                # 调用之前的连接函数
                await self.connect_to_server(
                    server_id=server_id,
                    toolkit_name=target_toolkit,
                    command=command,
                    args=processed_args,
                    env=full_env
                )

            except Exception as e:
                logger.error(f"加载 MCP 配置失败: {e}")
# 实例化全局单例
mcp_manager = MCPManager()