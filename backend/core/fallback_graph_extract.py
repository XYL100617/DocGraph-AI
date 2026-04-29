import re


VALID_ENTITY_TYPES = ["人物", "组织", "地点", "时间", "事件", "对象", "主题", "其他"]


def clean_text(text: str):
    return (text or "").strip()


def normalize_pure_text(text: str):
    return re.sub(r"[，,。！？；;\n\s]+", "", text or "")


def split_units(text: str):
    text = clean_text(text)
    parts = re.split(r"[，,。！？；;\n]+", text)

    units = []

    for p in parts:
        p = p.strip()
        if len(p) >= 2:
            units.append(p)

    return units


def is_short_text(text: str, max_len=60):
    pure = normalize_pure_text(text)

    if not pure:
        return False

    if len(pure) > max_len:
        return False

    if not re.search(r"[\u4e00-\u9fa5]", pure):
        return False

    return True


def guess_type(text: str):
    if not text:
        return "其他"

    text = str(text)

    if any(k in text for k in ["年", "月", "日", "时期", "时代", "阶段"]):
        return "时间"

    if any(k in text for k in ["公司", "学校", "大学", "团队", "机构", "单位", "部门", "学院", "集团"]):
        return "组织"

    if any(k in text for k in ["国家", "城市", "地区", "地点", "故乡", "家乡"]):
        return "地点"

    if any(k in text for k in ["问题", "错误", "失败", "异常", "困难", "活动", "任务", "会议", "事件", "行为", "过程", "现象"]):
        return "事件"

    if any(k in text for k in ["系统", "平台", "模块", "工具", "文件", "文档", "图片", "PDF", "项目", "水", "书", "课", "作业"]):
        return "对象"

    if any(k in text for k in ["算法", "模型", "方法", "技术", "思想", "观点", "理论", "概念", "主题", "精神", "情绪", "意象", "理想", "信念"]):
        return "主题"

    return "主题"


def guess_short_entity_type(name: str):
    """
    短文本内部节点类型判断。
    不追求完美，只保证比单节点图更合理。
    """
    name = (name or "").strip()

    if not name:
        return "其他"

    common_surnames = set(
        "赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦尤许何吕施张孔曹严华金魏陶姜谢邹喻柏水窦章云苏潘葛奚范彭郎鲁韦昌马苗凤花方俞任袁柳唐罗薛伍余米贝姚孟顾尹江钟高龚程邢裴陆荣翁"
    )

    # 小红、小明、小刚、小张、小李
    if re.fullmatch(r"小[\u4e00-\u9fa5]{1,2}", name):
        return "人物"

    # 常见中文姓名
    if 2 <= len(name) <= 3 and re.fullmatch(r"[\u4e00-\u9fa5]+", name) and name[0] in common_surnames:
        return "人物"

    action_keywords = [
        "喝", "吃", "看", "写", "读", "走", "跑", "学", "学习", "工作", "使用",
        "上传", "生成", "分析", "识别", "总结", "构建", "实现", "表达", "体现",
        "思念", "离别", "奋斗", "创新", "实践", "服务", "影响", "决定",
        "立", "纳", "载", "行", "知", "修", "治", "平"
    ]

    if any(k in name for k in action_keywords):
        return "事件"

    object_keywords = ["水", "书", "课", "图片", "文档", "PDF", "系统", "平台", "工具", "模块"]

    if any(k in name for k in object_keywords):
        return "对象"

    place_keywords = ["国", "国家", "故乡", "家乡", "天下", "天地", "城市"]

    if any(k in name for k in place_keywords):
        return "主题"

    emotion_keywords = ["思念", "悲伤", "快乐", "孤独", "希望", "梦想", "理想", "信念"]

    if any(k in name for k in emotion_keywords):
        return "主题"

    return guess_type(name)


def add_entity(entities, keywords, name, etype="主题", desc="语义节点"):
    name = (name or "").strip()

    if not name:
        return

    if name not in [e["name"] for e in entities]:
        entities.append({
            "name": name,
            "type": etype if etype in VALID_ENTITY_TYPES else "主题",
            "description": desc
        })
        keywords.append(name)


def add_relation(relations, source, target, relation="关联", confidence=0.7):
    if not source or not target or source == target:
        return

    key = (source, target, relation)

    existing = [
        (r["source"], r["target"], r["relation"])
        for r in relations
    ]

    if key not in existing:
        relations.append({
            "source": source,
            "target": target,
            "relation": relation,
            "confidence": confidence
        })


def extract_subject_action_object(pure: str):
    """
    非模型的轻量主谓宾尝试。
    适合“小红喝水”“学生学习算法”这类短句。
    """
    if not pure or len(pure) < 3:
        return None

    action_words = [
        "喝", "吃", "看", "写", "读", "学习", "学", "使用", "上传", "生成",
        "分析", "识别", "总结", "构建", "实现", "参加", "负责", "开发"
    ]

    for action in sorted(action_words, key=len, reverse=True):
        idx = pure.find(action)

        if idx > 0:
            subject = pure[:idx]
            rest = pure[idx + len(action):]

            if rest:
                event = action + rest
            else:
                event = action

            return subject, event, rest

    return None


def infer_text_type(text: str):
    pure = normalize_pure_text(text)

    if not pure:
        return "其他"

    if extract_subject_action_object(pure):
        return "普通行为句"

    if any(k in pure for k in ["月", "风", "花", "雪", "夜", "故乡", "离别", "思念", "梦", "心"]):
        return "诗句歌词"

    if len(pure) <= 12 and any(k in pure for k in ["德", "道", "志", "学", "知", "行", "仁", "义", "天下", "国家", "太平", "自强", "不息"]):
        return "名言格言"

    if len(pure) <= 20:
        return "标题短语"

    return "其他"


def build_summary(text_type, main, entities, relations):
    if text_type == "普通行为句":
        return f"该短句描述了“{main}”这一具体行为或事件。"

    if text_type == "诗句歌词":
        return f"该文本包含“{main}”中的意象、情绪或场景信息。"

    if text_type == "名言格言":
        return f"该短句表达了“{main}”中的思想、态度或抽象主题。"

    if text_type == "标题短语":
        return f"该短文本围绕“{main}”形成基础语义结构。"

    return f"该文本描述了“{main}”的基本语义内容。"


def short_text_graph_extract(text: str):
    """
    通用短文本兜底抽取。
    用于 LLM 结果过弱时补图。
    """
    text = clean_text(text)
    pure = normalize_pure_text(text)

    if not is_short_text(text):
        return None

    entities = []
    relations = []
    keywords = []

    main = pure
    text_type = infer_text_type(text)

    add_entity(
        entities,
        keywords,
        main,
        "主题",
        "短文本整体语义"
    )

    # 1. 普通行为句：小红喝水 / 学生学习算法
    sao = extract_subject_action_object(pure)

    if sao:
        subject, event, obj = sao

        if subject:
            add_entity(
                entities,
                keywords,
                subject,
                guess_short_entity_type(subject),
                "行为主体"
            )
            add_relation(relations, subject, event, "参与", 0.78)

        if event:
            add_entity(
                entities,
                keywords,
                event,
                "事件",
                "短句中的行为或动作"
            )
            add_relation(relations, main, event, "描述", 0.72)

        if obj and obj != event:
            add_entity(
                entities,
                keywords,
                obj,
                guess_short_entity_type(obj),
                "行为涉及对象"
            )
            add_relation(relations, event, obj, "关联", 0.65)

    # 2. 因果/条件：少年强则国强
    if "则" in pure:
        left, right = pure.split("则", 1)

        if left and right:
            add_entity(entities, keywords, left, guess_short_entity_type(left), "条件或前提")
            add_entity(entities, keywords, right, guess_short_entity_type(right), "结果或影响")
            add_relation(relations, left, right, "导致", 0.82)
            add_relation(relations, main, left, "包含", 0.66)
            add_relation(relations, main, right, "包含", 0.66)

    # 3. “为X做Y”结构
    if pure.startswith("为") and len(pure) >= 4:
        body = pure[1:]

        action_candidates = ["立心", "立命", "继绝学", "开太平", "服务", "奋斗", "求知", "创新"]

        matched = False

        for act in action_candidates:
            if act in body:
                obj = body.replace(act, "")

                if obj:
                    add_entity(entities, keywords, obj, guess_short_entity_type(obj), "作用对象")

                add_entity(entities, keywords, act, "事件", "短句中的行为或价值动作")

                if obj:
                    add_relation(relations, act, obj, "服务于", 0.78)

                add_relation(relations, main, act, "体现", 0.72)
                matched = True

        if not matched and len(body) >= 4:
            mid = len(body) // 2
            obj = body[:mid]
            act = body[mid:]

            add_entity(entities, keywords, obj, guess_short_entity_type(obj), "作用对象")
            add_entity(entities, keywords, act, guess_short_entity_type(act), "行为或价值表达")

            add_relation(relations, act, obj, "服务于", 0.65)
            add_relation(relations, main, act, "体现", 0.62)

    # 4. 统一/融合结构：知行合一
    for key in ["合一", "统一", "融合"]:
        if pure.endswith(key) and len(pure) > len(key):
            front = pure[:-len(key)]
            chunks = [
                front[i:i + 2]
                for i in range(0, len(front), 2)
                if len(front[i:i + 2]) >= 2
            ]

            for c in chunks:
                add_entity(entities, keywords, c, guess_short_entity_type(c), "统一关系中的语义对象")
                add_relation(relations, main, c, "包含", 0.7)

            add_entity(entities, keywords, key, "主题", "统一或融合关系")
            add_relation(relations, main, key, "体现", 0.75)

    # 5. 四字格/短语通用切分
    if len(entities) <= 2:
        if len(pure) in [4, 6, 8, 10, 12]:
            chunks = [
                pure[i:i + 2]
                for i in range(0, len(pure), 2)
                if len(pure[i:i + 2]) >= 2
            ]
        else:
            chunks = [
                pure[i:i + 2]
                for i in range(0, min(len(pure), 12) - 1, 2)
                if len(pure[i:i + 2]) >= 2
            ]

        for chunk in chunks[:6]:
            if chunk == main:
                continue

            add_entity(
                entities,
                keywords,
                chunk,
                guess_short_entity_type(chunk),
                "短文本中的局部语义"
            )
            add_relation(relations, main, chunk, "包含", 0.62)

    # 6. 抽象补充节点：只在诗句/名言/标题中使用，普通行为句不强行拔高
    abstract_nodes = []

    if text_type in {"名言格言", "诗句歌词", "标题短语"}:
        if any(k in pure for k in ["德", "仁", "义", "礼", "信", "修"]):
            abstract_nodes.append("道德修养")

        if any(k in pure for k in ["知", "学", "求", "问"]):
            abstract_nodes.append("学习求知")

        if any(k in pure for k in ["行", "实践", "做"]):
            abstract_nodes.append("实践行动")

        if any(k in pure for k in ["强", "奋斗", "不息", "志"]):
            abstract_nodes.append("奋斗精神")

        if any(k in pure for k in ["国", "天下", "太平", "民"]):
            abstract_nodes.append("家国情怀")

        if any(k in pure for k in ["海", "百川", "容", "纳"]):
            abstract_nodes.append("开放包容")

        if any(k in pure for k in ["月", "夜", "风", "花", "雪", "故乡", "离别", "思念"]):
            abstract_nodes.append("意象情绪")

        if any(k in pure for k in ["心", "命", "理想", "信念"]):
            abstract_nodes.append("价值追求")

    for node in abstract_nodes:
        add_entity(entities, keywords, node, "主题", "短文本表达的抽象含义")
        add_relation(relations, main, node, "体现", 0.7)

    # 7. 最终兜底：至少两个节点
    if len(entities) <= 1 and len(pure) >= 4:
        left = pure[:len(pure) // 2]
        right = pure[len(pure) // 2:]

        add_entity(entities, keywords, left, guess_short_entity_type(left), "短文本前半部分语义")
        add_entity(entities, keywords, right, guess_short_entity_type(right), "短文本后半部分语义")
        add_relation(relations, main, left, "包含", 0.6)
        add_relation(relations, main, right, "包含", 0.6)

    return {
        "summary": build_summary(text_type, main, entities, relations),
        "text_type": text_type,
        "entities": entities,
        "relations": relations,
        "keywords": keywords,
        "modules": [{"module": "识别内容", "text": text}],
        "repaired_text": text,
        "visual_notes": [],
        "source": "short_text_fallback_graph_extract"
    }


def fallback_graph_extract(text: str):
    """
    通用兜底抽取：
    解决短文本、OCR噪声、AI抽取失败时的空图/弱图问题。
    """

    text = clean_text(text)

    if not text:
        return {
            "summary": "",
            "text_type": "其他",
            "entities": [],
            "relations": [],
            "keywords": [],
            "modules": [],
            "repaired_text": "",
            "visual_notes": [],
            "source": "fallback_graph_extract"
        }

    # 短文本专门补图
    short_result = short_text_graph_extract(text)

    if short_result:
        return short_result

    units = split_units(text)
    main_name = text.replace("\n", "，").strip()
    main_display = main_name if len(main_name) <= 30 else main_name[:30] + "..."

    entities = []
    relations = []
    keywords = []

    add_entity(
        entities,
        keywords,
        main_display,
        "主题",
        "系统根据输入文本自动生成的主题节点"
    )

    for unit in units[:8]:
        if unit == main_display:
            continue

        unit_type = guess_type(unit)

        add_entity(
            entities,
            keywords,
            unit,
            unit_type,
            "由文本片段生成的语义节点"
        )

        add_relation(
            relations,
            main_display,
            unit,
            "包含",
            0.6
        )

    summary = main_display if len(main_display) <= 80 else main_display[:80] + "..."

    return {
        "summary": summary,
        "text_type": "文档内容",
        "entities": entities,
        "relations": relations,
        "keywords": keywords,
        "modules": [{"module": "识别内容", "text": text}],
        "repaired_text": text,
        "visual_notes": [],
        "source": "fallback_graph_extract"
    }