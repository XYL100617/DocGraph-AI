import re

try:
    import jieba.posseg as pseg
except Exception:
    pseg = None


VALID_ENTITY_TYPES = {
    "人物", "时间", "地点", "对象", "事件", "组织",
    "主题", "方法", "结果", "概念", "文件", "其他"
}


TYPE_MAP = {
    "人": "人物",
    "人名": "人物",
    "角色": "人物",

    "日期": "时间",
    "年代": "时间",

    "机构": "组织",
    "学校": "组织",
    "公司": "组织",

    "技术": "方法",
    "算法": "方法",
    "模型": "方法",
    "策略": "方法",
    "方案": "方法",
    "机制": "方法",
    "流程": "方法",

    "理论": "概念",
    "原理": "概念",
    "定义": "概念",
    "术语": "概念",

    "问题": "事件",
    "错误": "事件",
    "异常": "事件",

    "文档": "文件",
    "PDF": "文件",
    "图片": "文件",
    "图像": "文件",
    "表格": "文件",

    "输出": "结果",
    "结论": "结果",
    "成果": "结果",
    "效果": "结果",
}


PERSON_SURNAMES = set(
    "赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦尤许何吕施张孔曹严华金魏陶姜谢邹喻柏水窦章云苏潘葛奚范彭郎鲁韦昌马苗凤花方俞任袁柳唐罗薛伍余米贝姚孟顾尹江钟高龚程邢裴陆荣翁"
)

ORG_SUFFIXES = (
    "公司", "大学", "学院", "学校", "研究院", "实验室",
    "中心", "部门", "集团", "委员会", "单位", "机构",
    "团队", "组织", "协会", "政府", "军队"
)

COMMON_PLACE_NAMES = {
    "北京", "上海", "广州", "深圳", "杭州", "南京", "武汉", "西安",
    "郑州", "成都", "重庆", "天津", "苏州", "长沙", "青岛", "厦门",
    "洛阳", "开封", "纽约", "伦敦", "巴黎", "东京"
}


def normalize_12_type(t: str):
    t = str(t or "主题").strip()
    t = TYPE_MAP.get(t, t)
    return t if t in VALID_ENTITY_TYPES else "主题"


def add(scores, key, value):
    if key in scores:
        scores[key] += value


def contains_any(text, words):
    text = str(text or "")
    return any(w in text for w in words)


def is_clear_time(name: str):
    name = str(name or "").strip()

    if re.fullmatch(r"\d{2,4}年", name):
        return True
    if re.fullmatch(r"\d{1,2}月", name):
        return True
    if re.fullmatch(r"\d{1,2}日", name):
        return True
    if re.search(r"\d{2,4}年[-—~至到]\d{2,4}年", name):
        return True
    if re.search(r"\d{2,4}年\d{1,2}月|\d{1,2}月\d{1,2}日", name):
        return True
    if re.fullmatch(r"\d{1,2}:\d{1,2}", name):
        return True
    if name in {"今天", "明天", "昨天", "上午", "下午", "晚上", "早上", "中午"}:
        return True

    return False


def guess_pos_type_by_jieba(name: str):
    """
    jieba 词性辅助：
    ns = 地点
    nr = 人名
    nt = 组织
    """
    if pseg is None:
        return ""

    try:
        words = list(pseg.cut(name))
    except Exception:
        return ""

    if not words:
        return ""

    flags = [w.flag for w in words]

    if "nr" in flags:
        return "人物"

    if "nt" in flags:
        return "组织"

    if "ns" in flags:
        return "地点"

    return ""


def infer_entity_type(name: str, old_type: str = "主题"):
    name = str(name or "").strip()
    old_type = normalize_12_type(old_type)

    if not name:
        return "其他"

    scores = {t: 0 for t in VALID_ENTITY_TYPES}

    # LLM 原类型只给基础分，不能完全相信
    add(scores, old_type, 1)

    # LTP / LLM 如果已经明确给出人物、地点、组织，额外加权
    if old_type in {"人物", "地点", "组织"}:
        add(scores, old_type, 4)

    # jieba 词性辅助，解决“杭州/北京/上海”等无后缀地名
    pos_type = guess_pos_type_by_jieba(name)
    if pos_type:
        add(scores, pos_type, 6)

    # =====================
    # 人物 / 群体
    # =====================
    if re.fullmatch(r"小[\u4e00-\u9fa5]{1,2}", name):
        add(scores, "人物", 8)

    if name in {
        "老师", "学生", "作者", "用户", "管理员", "医生", "患者",
        "青年", "人民", "群众", "民众", "生民", "工人", "农民"
    }:
        add(scores, "人物", 7)

    if 2 <= len(name) <= 3 and re.fullmatch(r"[\u4e00-\u9fa5]+", name):
        if name[0] in PERSON_SURNAMES:
            add(scores, "人物", 5)

    if contains_any(name, ["青年", "人民", "群众", "民众", "生民"]):
        add(scores, "人物", 4)

    # =====================
    # 时间：只认明确时间格式
    # =====================
    if is_clear_time(name):
        add(scores, "时间", 10)

    # =====================
    # 组织
    # =====================
    if name.endswith(ORG_SUFFIXES):
        add(scores, "组织", 9)

    if contains_any(name, ["共产党", "共青团", "政府", "军队", "志愿军", "联合国", "委员会", "协会", "学生会"]):
        add(scores, "组织", 8)

    # =====================
    # 地点
    # =====================
    if name in COMMON_PLACE_NAMES:
        add(scores, "地点", 9)

    if contains_any(name, [
        "国家", "城市", "地区", "省", "市", "县", "地点", "战场",
        "高地", "湖", "山", "河", "村", "镇", "港", "湾", "路",
        "街", "区", "校区", "广场", "机场", "车站"
    ]):
        add(scores, "地点", 6)

    # 组织后缀比地点后缀优先
    if name.endswith(("大学", "学院", "学校", "公司", "中心", "部门", "实验室")):
        add(scores, "地点", -6)

    # =====================
    # 文件
    # =====================
    if contains_any(name, ["文件", "文档", "PDF", "图片", "图像", "表格", "代码文件", "数据文件"]):
        add(scores, "文件", 8)

    if re.search(r"\.(py|vue|json|txt|pdf|docx|xlsx|png|jpg|jpeg)$", name, re.I):
        add(scores, "文件", 10)

    # =====================
    # 对象：系统、工具、设备、平台、具体物
    # =====================
    if contains_any(name, [
        "系统", "平台", "模块", "组件", "接口", "工具", "设备",
        "页面", "按钮", "代码", "数据库", "服务器", "前端", "后端",
        "缓存", "客户端", "服务端", "机票", "汉堡", "票据"
    ]):
        add(scores, "对象", 7)

    if name in {"水", "书", "电脑", "手机", "机票", "汉堡"}:
        add(scores, "对象", 7)

    if re.search(r"[A-Za-z]", name):
        if contains_any(name, ["API", "Vue", "FastAPI", "Qwen", "DeepSeek", "PaddleOCR", "NetworkX", "ECharts", "LTP"]):
            add(scores, "对象", 7)

    # =====================
    # 事件：动作、行为、问题、运动、战争、任务
    # =====================
    if contains_any(name, [
        "事件", "活动", "任务", "会议", "战争", "战役", "运动",
        "失败", "异常", "错误", "报错", "问题", "过程", "行为",
        "现象", "事故", "测试", "训练", "运行", "识别", "分析",
        "总结", "生成", "构建", "上传", "下载", "优化", "修复",
        "调用", "处理", "判断", "分类", "检测", "参与", "救国",
        "救民", "喝水", "吃", "买", "去", "到", "学习", "工作"
    ]):
        add(scores, "事件", 7)

    # 短动宾短语，如“买机票”“吃汉堡”“去杭州”
    if 2 <= len(name) <= 8 and re.search(r"(买|吃|喝|去|到|看|写|读|学|用|修|测|训|识别|生成|构建)", name):
        add(scores, "事件", 5)

    # =====================
    # 方法：做事方式、技术路线、算法模型、流程策略
    # =====================
    if contains_any(name, [
        "方法", "算法", "策略", "方案", "机制", "流程",
        "技术路线", "框架", "模型", "GraphRAG", "LightRAG",
        "PageRank", "中心性", "排序算法", "分类算法",
        "规则", "路径", "步骤"
    ]):
        add(scores, "方法", 8)

    # 工具名不要误判成方法
    if name in {"PaddleOCR", "NetworkX", "ECharts", "FastAPI", "Vue", "Qwen", "DeepSeek"}:
        add(scores, "对象", 8)
        add(scores, "方法", -3)

    # =====================
    # 结果
    # =====================
    if contains_any(name, [
        "结果", "输出", "结论", "效果", "成果", "报告",
        "摘要", "总结结果", "分析结果", "识别结果", "图谱结果",
        "准确率", "速度提升", "性能提升", "错误减少", "完成"
    ]):
        add(scores, "结果", 8)

    # 典型结果短语
    if re.search(r"(提升|降低|减少|增加|完成|解决|得到|形成|实现).{0,8}$", name):
        add(scores, "结果", 5)

    # =====================
    # 概念：学术概念、理论、主义、原理、学科术语
    # =====================
    if contains_any(name, [
        "概念", "理论", "原理", "定义", "知识点", "术语",
        "公式", "定理", "规律", "辩证法", "唯物论",
        "马克思主义", "社会主义", "资本主义", "阶级",
        "资产阶级", "无产阶级", "生产力", "生产关系",
        "国情", "共和国"
    ]):
        add(scores, "概念", 9)

    if name.endswith(("主义", "理论", "原理", "法", "论")):
        add(scores, "概念", 7)

    # =====================
    # 主题：价值、精神、态度、宏观表达
    # =====================
    if contains_any(name, [
        "思想", "观点", "理念", "精神", "价值", "理想",
        "信念", "力量", "重要性", "意象", "情绪", "主题",
        "初心", "忠诚", "形势", "使命", "责任", "态度",
        "情怀"
    ]):
        add(scores, "主题", 8)

    if name.endswith(("精神", "情怀", "价值", "力量", "重要性")):
        add(scores, "主题", 8)

    # =====================
    # 防误判
    # =====================

    # “时代/时期/阶段”不是明确时间
    if contains_any(name, ["时代", "时期", "阶段"]):
        add(scores, "时间", -8)
        add(scores, "主题", 3)

    # 月亮类不是时间
    if name in {"月亮", "明月", "月光", "岁月"}:
        add(scores, "时间", -8)
        add(scores, "主题", 5)

    # 抽象表达不能被对象/时间误伤
    if len(name) >= 4 and contains_any(name, ["精神", "思想", "价值", "国情", "形势", "力量", "重要性", "主义", "理论"]):
        add(scores, "对象", -6)
        add(scores, "时间", -6)

    # 组织优先于地点
    if scores["组织"] >= 7:
        add(scores, "地点", -5)

    # 文件优先于对象
    if scores["文件"] >= 7:
        add(scores, "对象", -4)

    # 概念优先于主题：理论/主义/法/论类不要全进主题
    if scores["概念"] >= 7:
        add(scores, "主题", -2)

    # 人物优先
    if scores["人物"] >= 7:
        add(scores, "主题", -3)
        add(scores, "事件", -3)
        add(scores, "时间", -3)

    best_type, best_score = max(scores.items(), key=lambda x: x[1])

    if best_score <= 1:
        return "主题"

    return best_type


def refine_entity_types(llm_result):
    if not isinstance(llm_result, dict):
        return llm_result

    entities = llm_result.get("entities", [])

    if not isinstance(entities, list):
        llm_result["entities"] = []
        return llm_result

    refined = []
    seen = set()

    for e in entities:
        if not isinstance(e, dict):
            continue

        name = str(e.get("name", "")).strip()
        old_type = e.get("type", "主题")

        if not name:
            continue

        new_type = infer_entity_type(name, old_type)

        e["type"] = new_type
        e["category"] = new_type

        if name in seen:
            continue

        seen.add(name)
        refined.append(e)

    llm_result["entities"] = refined
    return llm_result