import re
import networkx as nx

VALID_ENTITY_TYPES = {
    "人物", "时间", "地点", "对象", "事件", "组织",
    "主题", "方法", "结果", "概念", "文件", "其他"
}
VALID_RELATIONS = {
    "提出", "描述", "包含", "属于", "影响", "导致",
    "服务于", "体现", "关联", "参与", "负责", "使用", "生成"
}

ENTITY_TYPE_MAP = {
    "人": "人物", "人名": "人物", "角色": "人物", "作者": "人物", "老师": "人物", "学生": "人物", "成员": "人物",
    "机构": "组织", "公司": "组织", "学校": "组织", "团队": "组织", "部门": "组织", "单位": "组织",
    "地点": "地点", "国家": "地点", "城市": "地点", "地区": "地点",
    "时间": "时间", "日期": "时间", "年代": "时间", "时期": "时间",
    "事情": "事件", "事件": "事件", "活动": "事件", "任务": "事件", "会议": "事件", "上线": "事件", "发布": "事件",
    "问题": "事件", "错误": "事件", "异常": "事件", "缺陷": "事件", "噪声": "事件", "现象": "事件", "行为": "事件", "过程": "事件",
    "系统": "对象", "平台": "对象", "模块": "对象", "组件": "对象", "设备": "对象", "工具": "对象", "项目": "对象",
    "文件": "对象", "文档": "对象", "图片": "对象", "图像": "对象", "PDF": "对象", "表格": "对象",
    "方案": "主题", "策略": "主题", "机制": "主题", "技术": "主题", "算法": "主题", "模型": "主题", "框架": "主题", "协议": "主题", "流程": "主题", "方法": "主题",
    "思想": "主题", "观点": "主题", "理论": "主题", "原理": "主题", "概念": "主题", "主题": "主题", "结果": "主题", "输出": "主题", "结论": "主题",
    "技术": "方法", "算法": "方法", "模型": "方法", "策略": "方法", "方案": "方法", "机制": "方法", "流程": "方法",
    "输出": "结果", "结论": "结果", "成果": "结果", "效果": "结果", "摘要": "结果",
    "理论": "概念", "原理": "概念", "定义": "概念", "知识点": "概念", "术语": "概念",
    "文档": "文件", "PDF": "文件", "图片": "文件", "图像": "文件", "表格": "文件", "代码文件": "文件", "其他": "其他",
}

RELATION_MAP = {
    "提出": "提出", "表达": "描述", "描述": "描述", "说明": "描述",
    "包含": "包含", "包括": "包含", "组成": "包含", "由...组成": "包含",
    "属于": "属于", "是": "属于",
    "影响": "影响", "导致": "导致", "造成": "导致", "引起": "导致",
    "为了": "服务于", "面向": "服务于", "服务": "服务于", "服务于": "服务于",
    "体现": "体现", "反映": "体现",
    "参与": "参与", "负责": "负责", "开发": "负责", "设计": "负责",
    "使用": "使用", "采用": "使用", "用到": "使用", "用于": "使用", "应用": "使用", "应用于": "使用",
    "产生": "生成", "生成": "生成", "构建": "生成", "输出": "生成",
    "相关": "关联", "关联": "关联", "related_to": "关联"
}

RELATION_PRIORITY = ["使用", "负责", "参与", "提出", "生成", "导致", "影响", "服务于", "体现", "包含", "属于", "描述", "关联"]

NON_PERSON_KEYWORDS = {
    "系统", "平台", "模块", "组件", "算法", "模型", "框架", "协议", "方法", "策略", "流程", "技术", "文件", "文档", "图谱", "数据", "接口", "事件", "会议", "任务", "公司", "大学", "学院", "研究院", "中心", "委员会", "部门", "项目"
}

ORG_SUFFIXES = ("公司", "大学", "学院", "研究院", "实验室", "中心", "委员会", "部门", "集团", "学校", "单位")
PERSON_SURNAMES = set("赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦尤许何吕施张孔曹严华金魏陶姜谢邹喻柏水窦章云苏潘葛奚范彭郎鲁韦昌马苗凤花方俞任袁柳唐罗薛伍余米贝姚孟顾尹江钟高龚程邢裴陆荣翁")


def normalize_entity_type(entity_type: str) -> str:
    if not entity_type:
        return "主题"
    entity_type = str(entity_type).strip()
    for part in re.split(r"[\/,;，；|、]", entity_type):
        part = part.strip()
        if not part:
            continue
        mapped = ENTITY_TYPE_MAP.get(part, part)
        if mapped in VALID_ENTITY_TYPES:
            return mapped
    return ENTITY_TYPE_MAP.get(entity_type, "主题")


def normalize_relation(relation: str) -> str:
    if not relation:
        return "关联"
    relation = str(relation).strip()
    candidates = []
    for part in re.split(r"[\/,;，；|、]", relation):
        part = part.strip()
        if not part:
            continue
        mapped = RELATION_MAP.get(part, part)
        if mapped in VALID_RELATIONS:
            candidates.append(mapped)
    if not candidates:
        return RELATION_MAP.get(relation, "关联")
    for rel in RELATION_PRIORITY:
        if rel in candidates:
            return rel
    return candidates[0]


def infer_type_from_name(name: str, old_type: str = "主题") -> str:
    if not name:
        return old_type or "主题"
    name = str(name).strip()
    old_type = normalize_entity_type(old_type)
    if old_type != "主题":
        return old_type

    if any(name.endswith(s) for s in ORG_SUFFIXES):
        return "组织"
    if any(k in name for k in ["年", "月", "日", "时期", "时代"]):
        return "时间"
    if any(k in name for k in ["国家", "城市", "地区", "地点"]):
        return "地点"
    if any(k in name for k in ["事件", "会议", "活动", "任务", "上线", "发布", "问题", "错误", "异常", "缺陷", "噪声", "失败", "现象", "过程", "行为"]):
        return "事件"
    if any(k in name for k in ["系统", "平台", "模块", "组件", "接口", "设备", "工具", "项目", "文件", "文档", "图片", "图像", "PDF", "表格"]):
        return "对象"
    if any(k in name for k in ["算法", "模型", "网络", "框架", "协议", "流程", "技术", "方法", "策略", "方案", "机制", "结果", "输出", "图谱", "摘要", "总结", "思想", "观点", "理论", "原理", "概念"]):
        return "主题"

    if 2 <= len(name) <= 3 and re.fullmatch(r"[\u4e00-\u9fa5]+", name) and name[0] in PERSON_SURNAMES and not any(k in name for k in NON_PERSON_KEYWORDS):
        return "人物"

    return "主题"


def build_ltp_type_map(llm_result):
    ltp_type_map = {}
    for e in llm_result.get("ltp_entities", []):
        if isinstance(e, dict) and e.get("name") and e.get("type"):
            ltp_type_map[str(e["name"]).strip()] = normalize_entity_type(e["type"])
    for e in llm_result.get("entities", []):
        if isinstance(e, dict) and e.get("source") == "ltp" and e.get("name") and e.get("type"):
            ltp_type_map[str(e["name"]).strip()] = normalize_entity_type(e["type"])
    return ltp_type_map


def choose_entity_type(name: str, ai_type: str, ltp_type_map: dict) -> str:
    name = str(name or "").strip()
    ai_type = normalize_entity_type(ai_type)
    ltp_type = ltp_type_map.get(name)

    if not name:
        return "其他"

    # 1. LTP 对人物/组织/地点优先级最高
    if ltp_type in {"人物", "组织", "地点"}:
        return ltp_type

    # 2. 明确人物
    if re.fullmatch(r"小[\u4e00-\u9fa5]{1,2}", name):
        return "人物"

    if name in {"老师", "学生", "用户", "作者", "管理员", "医生", "患者"}:
        return "人物"

    if 2 <= len(name) <= 3 and re.fullmatch(r"[\u4e00-\u9fa5]+", name):
        if name[0] in PERSON_SURNAMES and not any(k in name for k in NON_PERSON_KEYWORDS):
            return "人物"

    # 3. 明确组织
    if any(name.endswith(s) for s in ORG_SUFFIXES):
        return "组织"

    # 4. 时间：避免“明月/月亮/月光”误判
    if name not in {"明月", "月亮", "月光", "岁月"}:
        if re.search(r"\d{2,4}年|\d{1,2}月|\d{1,2}日|上午|下午|晚上|今天|明天|昨天", name):
            return "时间"

    # 5. 事件：动作、行为、问题、异常
    event_words = [
        "喝", "吃", "看", "写", "读", "学习", "上传", "下载",
        "识别", "分析", "总结", "生成", "构建", "运行", "训练",
        "测试", "优化", "修复", "失败", "异常", "错误", "问题",
        "导致", "影响", "处理", "调用"
    ]
    if any(k in name for k in event_words):
        return "事件"

    # 6. 对象：系统、工具、文件、具体物
    object_words = [
        "系统", "平台", "模块", "组件", "接口", "工具", "文件",
        "文档", "图片", "图像", "PDF", "页面", "按钮", "代码",
        "数据集", "数据", "文本", "水", "书", "电脑", "手机"
    ]
    if any(k in name for k in object_words):
        return "对象"

    # 7. 技术工具名：英文/混合名优先对象或主题
    if re.search(r"[A-Za-z]", name):
        if any(k in name for k in ["OCR", "API", "Vue", "FastAPI", "Qwen", "DeepSeek", "PaddleOCR"]):
            return "对象"

    # 8. 抽象概念/方法/算法
    topic_words = [
        "思想", "观点", "理念", "理论", "方法", "技术", "算法",
        "模型", "策略", "方案", "机制", "原理", "概念",
        "知识图谱", "语义", "意象", "情绪", "精神", "价值",
        "理想", "信念", "中心性", "关系抽取"
    ]
    if any(k in name for k in topic_words):
        return "主题"

    # 9. 如果 AI 类型不是主题，且没有被上面推翻，就保留
    if ai_type in {"人物", "组织", "地点", "时间", "事件", "对象"}:
        return ai_type

    return "主题"

def build_graph(llm_result):
    entities = llm_result.get("entities", [])
    relations = llm_result.get("relations", [])
    ltp_type_map = build_ltp_type_map(llm_result)
    G = nx.DiGraph()

    for entity in entities:
        if isinstance(entity, str):
            name = entity.strip()
            ai_type = "主题"
            description = ""
            source = "llm"
        elif isinstance(entity, dict):
            name = str(entity.get("name", "")).strip()
            ai_type = entity.get("type", "主题")
            description = entity.get("description", "")
            source = entity.get("source", "llm")
        else:
            continue
        if not name:
            continue
        node_type = choose_entity_type(name, ai_type, ltp_type_map)
        G.add_node(name, id=name, name=name, label=name, type=node_type, category=node_type, group=0, description=description, source=source)

    for rel in relations:
        if not isinstance(rel, dict):
            continue
        source = rel.get("source") or rel.get("from")
        target = rel.get("target") or rel.get("to")
        relation = rel.get("relation") or rel.get("type") or "关联"
        raw_relation = rel.get("raw_relation") or relation
        confidence = rel.get("confidence", 0.7)
        if not source or not target:
            continue
        source = str(source).strip()
        target = str(target).strip()
        if not source or not target or source == target:
            continue
        relation = normalize_relation(relation)
        try:
            confidence = float(confidence)
        except Exception:
            confidence = 0.7
        confidence = max(0.0, min(confidence, 1.0))

        if source not in G:
            source_type = choose_entity_type(source, "主题", ltp_type_map)
            G.add_node(source, id=source, name=source, label=source, type=source_type, category=source_type, group=0, description="", source="relation_auto")
        if target not in G:
            target_type = choose_entity_type(target, "主题", ltp_type_map)
            G.add_node(target, id=target, name=target, label=target, type=target_type, category=target_type, group=0, description="", source="relation_auto")
        G.add_edge(source, target, relation=relation, raw_relation=raw_relation, label=relation, weight=confidence, confidence=confidence)

    nodes = []
    for node_id, attrs in G.nodes(data=True):
        node_type = choose_entity_type(node_id, attrs.get("type", "主题"), ltp_type_map)
        nodes.append({
            "id": node_id,
            "name": attrs.get("name", node_id),
            "label": attrs.get("label", node_id),
            "type": node_type,
            "category": node_type,
            "group": attrs.get("group", 0),
            "description": attrs.get("description", ""),
            "source": attrs.get("source", "llm"),
            "importance": 0,
            "symbolSize": 36
        })

    edges = []
    for source, target, attrs in G.edges(data=True):
        relation = normalize_relation(attrs.get("relation", "关联"))
        edges.append({
            "source": source,
            "target": target,
            "relation": relation,
            "raw_relation": attrs.get("raw_relation", relation),
            "label": relation,
            "weight": attrs.get("weight", 0.7),
            "confidence": attrs.get("confidence", 0.7)
        })

    return {"nodes": nodes, "edges": edges}
