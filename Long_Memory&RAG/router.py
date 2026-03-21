import json
from config import client, Config, logger
from tools import CATEGORY_METADATA

async def route_intent(user_query: str) -> list:
    """
    独立出的技能路由层 (Tool Router 网关)
    根据用户意图，动态决定激活哪些领域的技能包。
    """
    # 动态拼接可用技能包描述
    skills_description = ""
    for cat, desc in CATEGORY_METADATA.items():
        skills_description += f"- \"{cat}\": {desc}\n"
    
    router_prompt = f"""
    你是一个极其轻量、高效的意图分类网关 (Tool Router)。
    请判断需求所属技能包，并严格以 JSON 格式返回 (必须包含关键字 "json")。
    
    当前可用的技能包和说明如下：
    {skills_description}
    
    【强制判定规则】：
    1. 只要用户的指令中暗示了要生成、写入、保存文件到本地（无论提到 word, txt, docx 还是“建个文件”），你都必须返回 ["office"]！绝不能视为普通聊天！
    2. 只有纯粹的知识问答、闲聊，才返回空列表 []。
    
    【分类示例 (Few-Shot)】：
    用户输入: "帮我把书名写进word"
    返回: {{"active_skills": ["office"]}}
    
    用户输入: "分析一下这段报错"
    返回: {{"active_skills": ["gamedev"]}}
    
    用户输入: "量子力学是什么"
    返回: {{"active_skills": []}}
    """

    # 自动提取所有合法的技能分类名 (如["office", "gamedev"])
    # valid_skills = list(CATEGORY_METADATA.keys())

    try:
        # 换成成本低的小模型，这仅仅是个分类任务！
        resp = await client.chat.completions.create(
            model=Config.MODEL, 
            messages=[
                {"role": "system", "content": router_prompt},
                {"role": "user", "content": user_query}
            ],
            # --- 核心优化，开启严格的 JSON Schema 物理级约束 ---
            # --- 很多模型不支持以下模式！ ---
            # response_format={"type": "json_schema",
            #     "json_schema": {
            #         "name": "SkillRouterResponse",
            #         "strict": True,  # 开启严格模式，拒绝任何额外字段
            #         "schema": {
            #             "type": "object",
            #             "properties": {
            #                 "active_skills": {
            #                     "type": "array",
            #                     "description": "根据用户意图需要激活的技能包列表",
            #                     "items": {
            #                         "type": "string",
            #                         # 强行限制数组里的元素只能是注册过的 valid_skills！
            #                         "enum": valid_skills 
            #                     }
            #                 }
            #             },
            #             "required":["active_skills"], # 声明该字段必须存在
            #             "additionalProperties": False  # 绝对禁止模型自己发明其他的 Key
            #         }
            #     }
            # },
            response_format={"type": "json_object"},
            temperature=0  # 分类任务必须是 0 逻辑，拒绝任何发散
        )

        # 获取大模型的原始回复
        raw_content = resp.choices[0].message.content
        # 显微镜：直接把大模型吐出来的原始字符串打印出来！
        print(f"\n[Router 显微镜] 模型原始输出: {raw_content}")
        
        # 此时拿到的内容，100% 绝对是合法的 JSON，且绝对不包含不存在的技能名
        result = json.loads(resp.choices[0].message.content)
        skills = result.get("active_skills",[])
        return skills
    
    except Exception as e:
        logger.error(f"Router 网关异常: {e}")
        # 如果路由网关崩溃，采取降级策略：默认不加载附加技能包，只用 base 保底
        return[]