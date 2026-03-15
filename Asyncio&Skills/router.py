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
    请根据用户的需求，判断需要激活哪些领域的技能包。
    
    当前可用的附加技能包及说明如下：
    {skills_description}
    
    请严格以 JSON 格式返回，例如：{{"active_skills":["office", "gamedev"]}}
    如果用户的需求不属于上述任何分类（例如仅仅是普通的聊天问答、数学计算或通用搜索），请返回空的列表：{{"active_skills":[]}}
    """
    
    try:
        # 换成成本低的小模型，这仅仅是个分类任务！
        resp = await client.chat.completions.create(
            model=Config.MODEL, 
            messages=[
                {"role": "system", "content": router_prompt},
                {"role": "user", "content": user_query}
            ],
            response_format={"type": "json_object"},
            temperature=0  # 分类任务必须是 0 逻辑，拒绝任何发散
        )
        result = json.loads(resp.choices[0].message.content)
        skills = result.get("active_skills",[])
        return skills
    except Exception as e:
        logger.error(f"Router 网关异常: {e}")
        # 如果路由网关崩溃，采取降级策略：默认不加载附加技能包，只用 base 保底
        return[]