from fastapi import APIRouter, UploadFile, File, Form, BackgroundTasks
import asyncio
import shutil
import os
import json
import uuid

from core.entity_type_refine import refine_entity_types
from core.layout_repair_vl import should_use_vl_layout_repair, repair_layout_with_vl
from core.ocr import run_ocr_document
from core.llm import (
    quick_summary_text,
    quick_summary_ocr,
    graph_deep_extract
)
from core.vision_detector import detect_visual_element
from core.semantic_merge import semantic_merge_result
from core.relation_refine import refine_llm_relations
from graph.build import build_graph
from graph.community import add_community_to_graph
from graph.analysis import analyze_graph
from core.history import save_history
from utils.encoding_utils import read_text_auto


router = APIRouter()

UPLOAD_DIR = "storage/images"
CACHE_DIR = "storage/cache"
MAX_GRAPH_TEXT_LEN = 3500

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(CACHE_DIR, exist_ok=True)


def save_cache(task_id, data):
    path = os.path.join(CACHE_DIR, f"{task_id}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_cache(task_id):
    path = os.path.join(CACHE_DIR, f"{task_id}.json")
    if not os.path.exists(path):
        return None

    text = read_text_auto(path)
    return json.loads(text)


def get_text_for_ai(cache_or_ocr):
    """
    AI 输入文本统一提取。
    优先级：
    1. cache.text
    2. ocr.structured_text，也就是 ECLA 增强结果
    3. ocr.raw_text
    """
    if not cache_or_ocr:
        return ""

    if "ocr" in cache_or_ocr:
        ocr_result = cache_or_ocr.get("ocr", {})
        return (
            cache_or_ocr.get("text", "")
            or ocr_result.get("structured_text", "")
            or ocr_result.get("raw_text", "")
            or ""
        ).strip()

    return (
        cache_or_ocr.get("structured_text", "")
        or cache_or_ocr.get("raw_text", "")
        or ""
    ).strip()


def normalize_ocr_response(ocr_result):
    ocr_result = ocr_result or {}

    return {
        "raw_text": ocr_result.get("raw_text", ""),
        "structured_text": ocr_result.get("structured_text", ""),
        "layout_type": ocr_result.get("layout_type", ""),
        "modules": ocr_result.get("modules", []),
        "blocks": ocr_result.get("blocks", []),
        "lines": ocr_result.get("lines", []),
        "ecla_enabled": ocr_result.get("ecla_enabled", False),
        "raw_structured_text": ocr_result.get("raw_structured_text", ""),
        "raw_modules": ocr_result.get("raw_modules", [])
    }


def apply_analysis_to_graph(graph_data, analysis_result):
    nodes = graph_data.get("nodes", [])

    if len(nodes) == 1:
        nodes[0]["importance"] = 1
        nodes[0]["symbolSize"] = 42
        return graph_data

    fusion = analysis_result.get("metrics", {}).get("fusion", {})

    for node in nodes:
        node_id = node.get("id") or node.get("name")
        score = float(fusion.get(node_id, 0))
        node["importance"] = round(score, 4)
        node["symbolSize"] = 26 + score * 28

    return graph_data


def build_full_graph_pipeline(llm_result):
    llm_result = llm_result or {
        "summary": "",
        "entities": [],
        "relations": [],
        "keywords": []
    }

    try:
        llm_result = refine_entity_types(llm_result)
    except Exception as e:
        print("refine_entity_types 第一次失败，继续使用原始AI结果：", e)

    try:
        llm_result = semantic_merge_result(llm_result)
    except Exception as e:
        print("semantic_merge_result 失败，继续使用当前AI结果：", e)

    try:
        llm_result = refine_entity_types(llm_result)
    except Exception as e:
        print("refine_entity_types 第二次失败，继续构图：", e)

    try:
        llm_result = refine_llm_relations(llm_result)
    except Exception as e:
        print("refine_llm_relations 失败，继续构图：", e)

    graph_data = build_graph(llm_result)

    try:
        graph_data = add_community_to_graph(graph_data)
    except Exception as e:
        print("社区发现失败，保留默认group：", e)

    try:
        analysis_result = analyze_graph(graph_data)
    except Exception as e:
        print("多中心性分析失败：", e)
        analysis_result = {
            "core_nodes": [],
            "important_paths": [],
            "metrics": {
                "degree": {},
                "betweenness": {},
                "pagerank": {},
                "fusion": {}
            }
        }

    graph_data = apply_analysis_to_graph(graph_data, analysis_result)

    return llm_result, graph_data, analysis_result

def get_graph_summary(llm_result, analysis_result):
    llm_result = llm_result or {}

    graph_summary = (
        llm_result.get("graph_summary")
        or llm_result.get("deep_summary")
        or llm_result.get("deepAnalysis")
        or llm_result.get("analysis")
        or llm_result.get("summary")
        or ""
    )

    if graph_summary:
        return graph_summary

    core_nodes = analysis_result.get("core_nodes", []) if analysis_result else []
    core_names = "、".join([
        n.get("name", "")
        for n in core_nodes[:2]
        if n.get("name")
    ])

    if core_names:
        return f"AI已对识别内容进行进一步语义分析，核心信息集中在 {core_names} 等内容，并结合知识图谱完成结构化表达。"

    return "AI已对识别内容进行进一步语义分析，并结合知识图谱完成结构化表达。"

async def generate_graph_background(task_id: str, session_id: str = None):
    cache = load_cache(task_id)
    if not cache:
        return

    if cache.get("graph_status") == "done" and cache.get("graph"):
        return

    if cache.get("graph_status") == "running":
        return

    try:
        cache["graph_status"] = "running"
        cache["graph_error"] = ""
        save_cache(task_id, cache)

        extracted_text = get_text_for_ai(cache)

        if not extracted_text.strip():
            cache["graph_status"] = "failed"
            cache["graph_error"] = "OCR结果为空，无法生成图谱"
            save_cache(task_id, cache)
            return

        extracted_text = extracted_text[:MAX_GRAPH_TEXT_LEN]

        llm_result = graph_deep_extract(extracted_text)
        llm_result, graph_data, analysis_result = build_full_graph_pipeline(llm_result)

        graph_summary = get_graph_summary(llm_result, analysis_result)

        cache["ai_result"] = llm_result
        cache["graph"] = graph_data
        cache["analysis"] = analysis_result
        cache["graph_summary"] = graph_summary
        cache["deep_summary"] = graph_summary
        cache["graph_status"] = "done"
        cache["graph_error"] = ""
        save_cache(task_id, cache)

        if session_id:
            try:
                save_history(session_id, {
                    "text": cache.get("text", ""),
                    "ocr": cache.get("ocr", {}),
                    "result": llm_result,
                    "graph": graph_data,
                    "analysis": analysis_result
                })
            except Exception as e:
                print("历史记录保存失败：", e)

    except Exception as e:
        print("后台图谱生成失败：", e)
        cache = load_cache(task_id) or {}
        cache["graph_status"] = "failed"
        cache["graph_error"] = str(e)
        save_cache(task_id, cache)

@router.post("/upload/ocr-only")
async def upload_ocr_only(
    file: UploadFile = File(None),
    text: str = Form(None)
):
    task_id = uuid.uuid4().hex

    ocr_result = {
        "raw_text": "",
        "structured_text": "",
        "layout_type": "",
        "modules": [],
        "blocks": [],
        "lines": [],
        "ecla_enabled": False
    }

    extracted_text = ""
    file_path = None

    visual_detection = {
        "has_visual": False,
        "reason": "纯文本输入或未检测",
        "text_area_ratio": 0,
        "non_white_ratio": 0
    }

    if file:
        safe_filename = f"{uuid.uuid4().hex}_{file.filename}"
        file_path = os.path.join(UPLOAD_DIR, safe_filename)

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        ocr_result = run_ocr_document(file_path)
        ocr_result = normalize_ocr_response(ocr_result)

        extracted_text = get_text_for_ai(ocr_result)

        if file_path.lower().endswith((".jpg", ".jpeg", ".png", ".bmp", ".webp")):
            visual_detection = detect_visual_element(
                file_path,
                ocr_result.get("blocks", [])
            )

            if should_use_vl_layout_repair(ocr_result, visual_detection):
                try:
                    rebuilt = repair_layout_with_vl(file_path, ocr_result)

                    ocr_result["raw_structured_text"] = ocr_result.get("structured_text", "")
                    ocr_result["raw_modules"] = ocr_result.get("modules", [])

                    ocr_result["structured_text"] = rebuilt.get(
                        "structured_text",
                        ocr_result.get("structured_text", "")
                    )

                    ocr_result["modules"] = rebuilt.get(
                        "modules",
                        ocr_result.get("modules", [])
                    )

                    ocr_result["layout_type"] = rebuilt.get(
                        "layout_type",
                        "vl_layout_rebuilt"
                    )

                    extracted_text = get_text_for_ai(ocr_result)

                except Exception as e:
                    print("qwen-vl-plus版面重建失败，保留ECLA/OCR排版：", e)

    if text and text.strip():
        if extracted_text:
            extracted_text = (extracted_text + "\n" + text).strip()
        else:
            extracted_text = text.strip()

        if not file:
            ocr_result = {
                "raw_text": extracted_text,
                "structured_text": extracted_text,
                "layout_type": "text_input",
                "modules": [
                    {
                        "module": "文本输入",
                        "text": extracted_text,
                        "blocks": []
                    }
                ],
                "blocks": [],
                "lines": [],
                "ecla_enabled": False
            }

    save_cache(task_id, {
        "text": extracted_text,
        "file_path": file_path,
        "ocr": ocr_result,
        "visual_detection": visual_detection,
        "summary_result": None,
        "ai_result": None,
        "graph": None,
        "analysis": None,
        "graph_status": "pending",
        "graph_error": ""
    })

    return {
        "success": True,
        "task_id": task_id,
        "text": extracted_text,
        "file_path": file_path,
        "ocr": ocr_result,
        "visual_detection": visual_detection,
        "ecla": {
            "enabled": ocr_result.get("ecla_enabled", False),
            "layout_type": ocr_result.get("layout_type", ""),
            "module_count": len(ocr_result.get("modules", [])),
            "line_count": len(ocr_result.get("lines", [])),
            "block_count": len(ocr_result.get("blocks", []))
        }
    }


@router.post("/upload/ai-summary")
async def ai_summary_after_ocr(
    task_id: str = Form(None),
    session_id: str = Form(None)
):
    if not task_id:
        return {"success": False, "error": "缺少 task_id"}

    cache = load_cache(task_id)
    if not cache:
        return {"success": False, "error": "未找到OCR缓存，请重新上传"}

    extracted_text = get_text_for_ai(cache)
    ocr_result = cache.get("ocr", {})

    if not extracted_text.strip():
        return {"success": False, "error": "OCR结果为空，无法进行AI总结"}

    if ocr_result.get("layout_type") == "text_input":
        result = quick_summary_text(extracted_text)
    else:
        result = quick_summary_ocr(ocr_result)

    cache["summary_result"] = result
    cache["ai_result"] = None
    cache["graph_status"] = "pending"
    cache["graph_error"] = ""
    save_cache(task_id, cache)

    # 这里统一启动后台图谱生成
    asyncio.create_task(generate_graph_background(task_id, session_id=session_id))

    return {
        "success": True,
        "task_id": task_id,
        "result": result,
        "ecla": {
            "enabled": ocr_result.get("ecla_enabled", False),
            "layout_type": ocr_result.get("layout_type", "")
        }
    }


@router.post("/upload/graph")
async def graph_after_summary(
    task_id: str = Form(None),
    session_id: str = Form(None)
):
    if not task_id:
        return {"success": False, "error": "缺少 task_id"}

    cache = load_cache(task_id)
    if not cache:
        return {"success": False, "error": "未找到缓存，请重新上传"}

    # 1. 已完成：直接返回缓存，不重复调用大模型
    if cache.get("graph_status") == "done" and cache.get("graph"):
        graph_summary = (
            cache.get("graph_summary")
            or cache.get("deep_summary")
            or get_graph_summary(cache.get("ai_result", {}), cache.get("analysis", {}))
        )

        return {
            "success": True,
            "task_id": task_id,
            "status": "done",
            "llm": cache.get("ai_result", {}),
            "result": cache.get("ai_result", {}),
            "graph": cache.get("graph", {"nodes": [], "edges": []}),
            "analysis": cache.get("analysis", {}),
            "graphSummary": graph_summary,
            "deepSummary": graph_summary,
            "ecla": {
                "enabled": cache.get("ocr", {}).get("ecla_enabled", False),
                "layout_type": cache.get("ocr", {}).get("layout_type", "")
            }
        }

    # 2. 正在后台生成：不要重复生成
    if cache.get("graph_status") == "running":
        return {
            "success": True,
            "task_id": task_id,
            "status": "running",
            "message": "知识图谱正在生成中，请稍后再点击查看"
        }

    try:
        cache["graph_status"] = "running"
        cache["graph_error"] = ""
        save_cache(task_id, cache)

        extracted_text = get_text_for_ai(cache)

        if not extracted_text.strip():
            cache["graph_status"] = "failed"
            cache["graph_error"] = "OCR结果为空，无法生成图谱"
            save_cache(task_id, cache)
            return {"success": False, "error": "OCR结果为空，无法生成图谱"}

        extracted_text = extracted_text[:MAX_GRAPH_TEXT_LEN]

        result = graph_deep_extract(extracted_text)
        llm_result, graph_data, analysis_result = build_full_graph_pipeline(result)

        graph_summary = get_graph_summary(llm_result, analysis_result)

        cache["ai_result"] = llm_result
        cache["graph"] = graph_data
        cache["analysis"] = analysis_result
        cache["graph_summary"] = graph_summary
        cache["deep_summary"] = graph_summary
        cache["graph_status"] = "done"
        cache["graph_error"] = ""
        save_cache(task_id, cache)

    except Exception as e:
        print("图谱构建失败：", e)

        cache["graph_status"] = "failed"
        cache["graph_error"] = str(e)
        save_cache(task_id, cache)

        return {
            "success": False,
            "task_id": task_id,
            "status": "failed",
            "error": str(e),
            "llm": {
                "summary": "",
                "entities": [],
                "relations": [],
                "keywords": []
            },
            "result": {
                "summary": "",
                "entities": [],
                "relations": [],
                "keywords": []
            },
            "graph": {
                "nodes": [],
                "edges": []
            },
            "analysis": {
                "core_nodes": [],
                "important_paths": [],
                "metrics": {}
            }
        }

    if session_id:
        try:
            save_history(session_id, {
                "text": cache.get("text", ""),
                "ocr": cache.get("ocr", {}),
                "result": llm_result,
                "graph": graph_data,
                "analysis": analysis_result
            })
        except Exception as e:
            print("历史记录保存失败：", e)

    return {
        "success": True,
        "task_id": task_id,
        "status": "done",
        "llm": llm_result,
        "result": llm_result,
        "graph": graph_data,
        "analysis": analysis_result,
        "graphSummary": graph_summary,
        "deepSummary": graph_summary,
        "ecla": {
            "enabled": cache.get("ocr", {}).get("ecla_enabled", False),
            "layout_type": cache.get("ocr", {}).get("layout_type", "")
        }
    }

@router.post("/upload")
async def upload_file(
    file: UploadFile = File(None),
    text: str = Form(None),
    session_id: str = Form(None),
    background: BackgroundTasks = None
):
    """
    兼容旧前端上传接口。
    注意：
    图谱后台生成只在 ai_summary_after_ocr 中启动一次。
    这里不要重复 create_task(graph_after_summary)。
    """
    ocr_response = await upload_ocr_only(file=file, text=text)

    if not ocr_response.get("success"):
        return ocr_response

    task_id = ocr_response["task_id"]

    ai_response = await ai_summary_after_ocr(
        task_id=task_id,
        session_id=session_id
    )

    if not ai_response.get("success"):
        return ai_response

    return {
        "success": True,
        "task_id": task_id,
        "text": ocr_response.get("text", ""),
        "ocr": ocr_response.get("ocr", {}),
        "result": ai_response.get("result", {}),
        "graph": None,
        "analysis": None,
        "ecla": ocr_response.get("ecla", {}),
        "message": "AI总结已生成，ECLA版面增强结果已接入，图谱生成已在后台启动。"
    }