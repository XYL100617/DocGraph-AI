import re

try:
    import jieba
    import jieba.posseg as pseg
    import jieba.analyse
except Exception:
    jieba = None
    pseg = None


VALID_ENTITY_TYPES = {
    "人物", "组织", "地点", "时间", "事件", "对象", "主题", "其他"
}

DOMAIN_TERMS = {
    "PaddleOCR": "对象",
    "OCR": "主题",
    "GraphRAG": "主题",
    "GraphRAG-lite": "主题",
    "LightRAG": "主题",
    "NetworkX": "对象",
    "PageRank": "主题",
    "ECharts": "对象",
    "DeepSeek": "对象",
    "Qwen": "对象",
    "LLM": "主题",
    "FastAPI": "对象",
    "Vue": "对象",
    "知识图谱": "主题",
    "多中心性分析": "主题",
    "语义理解": "主题",
    "版面恢复": "事件",
    "OCR识别": "事件",
    "可视化展示": "事件",
    "后端调度": "事件",
}

RELATION_TRIGGERS = {
    "用于": "使用",
    "用来": "使用",
    "使用": "使用",
    "采用": "使用",
    "应用于": "使用",
    "基于": "使用",
    "通过": "使用",

    "生成": "生成",
    "构建": "生成",
    "形成": "生成",
    "输出": "生成",
    "产生": "生成",

    "导致": "导致",
    "造成": "导致",
    "引起": "导致",

    "影响": "影响",
    "促进": "影响",
    "推动": "影响",

    "包含": "包含",
    "包括": "包含",
    "组成": "包含",

    "属于": "属于",

    "提出": "提出",
    "表达": "体现",
    "体现": "体现",
    "反映": "体现",
    "象征": "体现",

    "参加": "参与",
    "参与": "参与",
    "负责": "负责",
}

METHOD_TRIGGERS = ["通过", "基于", "采用", "使用", "利用", "借助", "依靠"]
RESULT_TRIGGERS = ["实现", "生成", "得到", "输出", "形成", "完成", "提升", "降低", "解决"]

STOP_WORDS = {
    "这个", "一个", "一种", "进行", "通过", "可以", "需要",
    "现在", "没有", "就是", "如果", "因为", "所以", "然后",
    "以及", "对于", "实现", "模块", "内容", "结果"
}

PERSON_SURNAMES = set(
    "赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦尤许何吕施张孔曹严华金魏陶姜谢邹喻柏水窦章云苏潘葛奚范彭郎鲁韦昌马苗凤花方俞任袁柳唐罗薛伍余米贝姚孟顾尹江钟高龚程邢裴陆荣翁"
)


def clean_text(text: str):
    text = text or ""
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip()


def split_sentences(text: str):
    parts = re.split(r"[。！？；;\n]", text or "")
    return [p.strip() for p in parts if len(p.strip()) >= 2]


def normalize_node_text(name: str):
    name = str(name or "").strip()
    name = name.strip(" ：:，,。.;；、[]【】()（）")
    return name

def extract_method_result_entities(text: str):
    """
    通用抽取：
    通过/基于/采用/使用 A 实现/生成/得到 B
    A -> 方法
    B -> 结果
    """
    entities = []
    relations = []

    for sent in split_sentences(text):
        for m in METHOD_TRIGGERS:
            if m not in sent:
                continue

            left, right = sent.split(m, 1)

            for r in RESULT_TRIGGERS:
                if r not in right:
                    continue

                method_part, result_part = right.split(r, 1)

                method = method_part.strip(" ，,。；;")
                result = result_part.strip(" ，,。；;")

                if 2 <= len(method) <= 20:
                    entities.append({
                        "name": method,
                        "type": "方法",
                        "description": "由方法触发句式抽取得到"
                    })

                if 2 <= len(result) <= 24:
                    entities.append({
                        "name": result,
                        "type": "结果",
                        "description": "由结果触发句式抽取得到"
                    })

                if 2 <= len(method) <= 20 and 2 <= len(result) <= 24:
                    relations.append({
                        "source": method,
                        "target": result,
                        "relation": "生成",
                        "confidence": 0.78
                    })

    return entities, relations

def is_bad_entity(name: str):
    name = normalize_node_text(name)

    if not name:
        return True

    if len(name) <= 1:
        return True

    if len(name) > 26:
        return True

    if name in STOP_WORDS:
        return True

    if re.fullmatch(r"\d+", name):
        return True

    if re.fullmatch(r"[^\u4e00-\u9fa5A-Za-z0-9]+", name):
        return True

    return False


def guess_type(name: str, pos: str = ""):
    name = normalize_node_text(name)

    if not name:
        return "其他"

    if name in DOMAIN_TERMS:
        return DOMAIN_TERMS[name]

    if pos == "nr":
        return "人物"

    if pos in {"nt", "nz"}:
        return "组织"

    if pos == "ns":
        return "地点"

    if re.fullmatch(r"小[\u4e00-\u9fa5]{1,2}", name):
        return "人物"

    if 2 <= len(name) <= 3 and re.fullmatch(r"[\u4e00-\u9fa5]+", name):
        if name[0] in PERSON_SURNAMES:
            return "人物"

    if name.endswith(("公司", "大学", "学院", "学校", "研究院", "实验室", "中心", "部门", "集团", "委员会", "单位", "团队")):
        return "组织"

    if re.search(r"\d{2,4}年|\d{1,2}月|\d{1,2}日|上午|下午|晚上|今天|明天|昨天", name):
        return "时间"

    if any(k in name for k in ["国家", "城市", "地区", "省", "市", "县", "地点", "战场", "高地"]):
        return "地点"

    if any(k in name for k in [
        "战争", "战役", "活动", "任务", "会议", "发布", "上线", "失败",
        "异常", "问题", "过程", "行为", "现象", "事故", "错误", "识别",
        "分析", "总结", "生成", "构建", "上传", "下载", "运行", "训练",
        "测试", "优化", "修复", "调用", "喝水", "学习"
    ]):
        return "事件"

    if any(k in name for k in [
        "系统", "平台", "模块", "组件", "接口", "工具", "文件", "文档",
        "图片", "图像", "PDF", "项目", "表格", "页面", "按钮", "代码",
        "数据集", "数据", "文本", "水", "书", "电脑", "手机"
    ]):
        return "对象"

    if any(k in name for k in [
        "思想", "观点", "理念", "理论", "方法", "技术", "算法", "模型",
        "策略", "方案", "机制", "原理", "概念", "知识图谱", "语义",
        "意象", "情绪", "精神", "价值", "理想", "信念", "主义", "中心性"
    ]):
        return "主题"

    return "主题"


def add_entity(entity_map, name, entity_type="主题", score=0.5):
    name = normalize_node_text(name)

    if is_bad_entity(name):
        return

    entity_type = entity_type if entity_type in VALID_ENTITY_TYPES else "主题"

    old = entity_map.get(name)

    if not old or score > old.get("score", 0):
        entity_map[name] = {
            "name": name,
            "type": entity_type,
            "description": "",
            "score": round(float(score), 4)
        }


def extract_entities_by_rules(text: str):
    entity_map = {}

    for term, term_type in DOMAIN_TERMS.items():
        if term in text:
            add_entity(entity_map, term, term_type, 1.0)

    # 规则抽取：中文连续短语
    candidates = re.findall(r"[\u4e00-\u9fa5A-Za-z0-9\-]{2,20}", text)

    for c in candidates:
        c = normalize_node_text(c)
        if is_bad_entity(c):
            continue

        if any(k in c for k in DOMAIN_TERMS):
            add_entity(entity_map, c, guess_type(c), 0.75)

    # jieba TextRank
    if jieba is not None:
        try:
            keywords = jieba.analyse.textrank(
                text,
                topK=14,
                withWeight=True,
                allowPOS=("n", "nr", "ns", "nt", "nz", "vn", "v", "eng")
            )

            for word, weight in keywords:
                add_entity(entity_map, word, guess_type(word), float(weight))
        except Exception:
            pass

    # 词性补充
    if pseg is not None:
        try:
            for word, flag in pseg.cut(text):
                word = normalize_node_text(word)

                if is_bad_entity(word):
                    continue

                if flag in {"nr", "nt", "ns", "nz"}:
                    add_entity(entity_map, word, guess_type(word, flag), 0.85)
        except Exception:
            pass

    return list(entity_map.values())


def find_entity_in_text(fragment, entity_names):
    candidates = [e for e in entity_names if e and e in fragment]
    if candidates:
        return max(candidates, key=len)
    return None


def extract_trigger_relations(text: str, entities):
    relations = []
    entity_names = [e["name"] for e in entities]

    for sent in split_sentences(text):
        appeared = [e for e in entity_names if e in sent]

        if len(appeared) < 2:
            continue

        for trigger, rel_type in RELATION_TRIGGERS.items():
            if trigger not in sent:
                continue

            left, right = sent.split(trigger, 1)

            source = find_entity_in_text(left, entity_names)
            target = find_entity_in_text(right, entity_names)

            if source and target and source != target:
                relations.append({
                    "source": source,
                    "target": target,
                    "relation": rel_type,
                    "confidence": 0.82
                })

    return relations


def choose_main_entity(entities, text):
    if not entities:
        return ""

    scored = []

    for e in entities:
        name = e.get("name", "")
        etype = e.get("type", "主题")

        score = 0

        if etype in {"事件", "主题"}:
            score += 3

        if name in text:
            score += text.count(name) * 2

        if 3 <= len(name) <= 12:
            score += 1

        if any(k in name for k in ["战争", "精神", "系统", "项目", "图谱", "识别", "分析"]):
            score += 2

        scored.append((score, name))

    scored.sort(reverse=True)
    return scored[0][1] if scored else ""


def infer_relation_to_main(entity, main_name):
    name = entity.get("name", "")
    etype = entity.get("type", "主题")

    if name == main_name:
        return None

    if etype in {"人物", "组织"}:
        return "参与"

    if etype in {"时间", "地点"}:
        return "描述"

    if etype == "事件":
        return "包含"

    if any(k in name for k in ["精神", "主义", "忠诚", "勇敢", "信念", "理想", "意象", "情绪"]):
        return "体现"

    return "关联"


def extract_center_relations(text: str, entities):
    relations = []
    main = choose_main_entity(entities, text)

    if not main:
        return relations

    for e in entities:
        name = e.get("name", "")

        if not name or name == main:
            continue

        if name not in text:
            continue

        rel = infer_relation_to_main(e, main)

        if not rel:
            continue

        if rel in {"参与", "描述"}:
            source, target = name, main
        elif rel in {"包含", "体现"}:
            source, target = main, name
        else:
            source, target = main, name

        relations.append({
            "source": source,
            "target": target,
            "relation": rel,
            "confidence": 0.6
        })

    return relations


def extract_cooccurrence_relations(text: str, entities):
    relations = []
    entity_names = [e["name"] for e in entities]

    for sent in split_sentences(text):
        appeared = [e for e in entity_names if e in sent]

        if len(appeared) < 2:
            continue

        # 限制共现关系数量，避免满屏乱线
        appeared = appeared[:4]

        for i in range(len(appeared) - 1):
            source = appeared[i]
            target = appeared[i + 1]

            if source != target:
                relations.append({
                    "source": source,
                    "target": target,
                    "relation": "关联",
                    "confidence": 0.48
                })

    return relations


def dedupe_relations(relations):
    seen = set()
    result = []

    priority = {
        "导致": 9,
        "使用": 8,
        "生成": 8,
        "参与": 7,
        "负责": 7,
        "体现": 6,
        "包含": 6,
        "描述": 5,
        "影响": 5,
        "服务于": 5,
        "属于": 3,
        "关联": 1,
    }

    best = {}

    for r in relations:
        source = r.get("source")
        target = r.get("target")
        relation = r.get("relation", "关联")

        if not source or not target or source == target:
            continue

        key_pair = (source, target)
        old = best.get(key_pair)

        if old is None or priority.get(relation, 1) > priority.get(old.get("relation", "关联"), 1):
            best[key_pair] = r

    for r in best.values():
        key = (r["source"], r["target"], r["relation"])
        if key in seen:
            continue
        seen.add(key)
        result.append(r)

    return result


def local_extract(text: str):
    text = clean_text(text)

    if not text:
        return {
            "summary": "",
            "entities": [],
            "relations": [],
            "keywords": [],
            "source": "local_extractor"
        }

    entities = extract_entities_by_rules(text)
    method_entities, method_relations = extract_method_result_entities(text)

    for e in method_entities:
        add_entity(
            {x["name"]: x for x in entities},
            e["name"],
            e["type"],
            0.9
        )

    # 更稳的写法：直接合并并去重
    name_set = {e["name"] for e in entities}
    for e in method_entities:
        if e["name"] not in name_set:
            entities.append(e)
            name_set.add(e["name"])
    trigger_relations = extract_trigger_relations(text, entities)
    center_relations = extract_center_relations(text, entities)
    co_relations = extract_cooccurrence_relations(text, entities)

    relations = dedupe_relations(
    trigger_relations + method_relations + center_relations + co_relations
    )

    keywords = [e["name"] for e in entities[:10]]
    summary = text[:100] + "..." if len(text) > 100 else text

    return {
        "summary": summary,
        "entities": entities,
        "relations": relations,
        "keywords": keywords,
        "source": "local_extractor"
    }