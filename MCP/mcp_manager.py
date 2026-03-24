from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from tools import TOOLKIT_REGISTRY, TOOLKIT_METADATA
from config import logger
import contextlib

class MCPManager:
    def __init__(self):
        # AsyncExitStack 保证整个 Agent 运行期间 MCP 服务一直运行
        # 使用 async with 在进程结束时，连接就断了
        self.exit_stack = contextlib.AsyncExitStack()
        self.sessions = {}  # {toolkit_name: session}

    async def connect_to_server(self, toolkit_name: str, command: str, args: list, source="mcp"):
        """
        连接一个 MCP Server 并在 TOOLKIT_REGISTRY 中注册其所有工具
        """
        logger.info(f"正在连接 MCP Server: {toolkit_name}...")
        # 启动图纸，定义了要启动什么外部程序
        server_params = StdioServerParameters(command=command, args=args)
        
        # 1. 建立 stdio 传输并进入 context
        # stdio_client 根据图纸执行进程
        # enter_async_context 将进程连接到 AsyncExitStack 上保证存活
        # read_stream, write_stream 是 读数据管, 写数据管
        read_stream, write_stream = await self.exit_stack.enter_async_context(stdio_client(server_params))
        
        # 2. 创建并初始化会话
        # ClientSession 建立标准 MCP 协议对话（JSON-RPC 格式）
        session = await self.exit_stack.enter_async_context(ClientSession(read_stream, write_stream))
        await session.initialize()
        
        self.sessions[toolkit_name] = session
        
        # 3. 发现并注册工具
        tools_result = await session.list_tools()
        
        if toolkit_name not in TOOLKIT_REGISTRY:
            TOOLKIT_REGISTRY[toolkit_name] = {
                "description": TOOLKIT_METADATA.get(toolkit_name, f"外部 MCP 技能包: {toolkit_name}"),
                "tools": {},
                "schemas": []
            }

        for tool in tools_result.tools:
            tool_id = f"{source}_{toolkit_name}_{tool.name}"
            
            # --- 关键：定义代理执行函数 ---
            # 当 Agent 调用 mcp__xxx 时，实际上是把参数转发给 Node.js 进程
            async def mcp_proxy(tool_name_internal=tool.name, toolkit_internal=toolkit_name, **kwargs):
                current_session = self.sessions.get(toolkit_internal)
                if not current_session:
                    return "错误：MCP 会话已断开。"
                
                # 向外部进程发起远程过程调用 (RPC)
                result = await current_session.call_tool(tool_name_internal, arguments=kwargs)
                
                # 拼接返回结果
                output = []
                for content in result.content:
                    if hasattr(content, 'text'):
                        output.append(content.text)
                return "\n".join(output) if output else "执行成功，无回显。"

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
                    "description": f"[MCP] {tool.description}",
                    "parameters": tool.inputSchema
                }
            })
            
        logger.info(f"✅ 成功加载 MCP 工具箱: {toolkit_name}，共 {len(tools_result.tools)} 个工具。")

    async def close_all(self):
        """退出程序时优雅关闭所有 Node.js 进程"""
        await self.exit_stack.aclose()
        logger.info("所有 MCP Server 进程已安全关闭。")

# 实例化全局单例
mcp_manager = MCPManager()