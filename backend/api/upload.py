from fastapi import APIRouter, UploadFile, File, Form, BackgroundTasks
import asyncio
import shutil
import os
import json
import uuid
from core.entity_type_refine import refine_entity_types
from core.layout_repair_vl import should_use_vl_layout_repair, repair_layout_with_vl
from core.ocr import run_ocr_document
from core.llm import analyze_text, analyze_ocr_with_qwen, quick_summary_text, quick_summary_ocr, graph_deep_extract
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
    # 使用自动编码读取，兼容多种编码的缓存文件
    text = read_text_auto(path)
    return json.loads(text)


def apply_analysis_to_graph(graph_data, analysis_result):
    """
    将多中心性融合分数写回节点。
    注意：节点大小不要过大，避免前端图谱拥挤。
    """
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
    """
    AI结果 -> 实体类型修正 -> 语义合并 -> 再次类型修正
    -> 关系修正 -> NetworkX建图 -> 社区发现 -> 多中心性分析
    """

    llm_result = llm_result or {
        "summary": "",
        "entities": [],
        "relations": [],
        "keywords": []
    }

    # 1. 第一次实体类型修正
    try:
        llm_result = refine_entity_types(llm_result)
    except Exception as e:
        print("refine_entity_types 第一次失败，继续使用原始AI结果：", e)

    # 2. 语义合并
    try:
        llm_result = semantic_merge_result(llm_result)
    except Exception as e:
        print("semantic_merge_result 失败，继续使用当前AI结果：", e)

    # 3. 合并后再次修正实体类型
    try:
        llm_result = refine_entity_types(llm_result)
    except Exception as e:
        print("refine_entity_types 第二次失败，继续构图：", e)

    # 4. 关系修正
    try:
        llm_result = refine_llm_relations(llm_result)
    except Exception as e:
        print("refine_llm_relations 失败，继续构图：", e)

    # 5. 构建图谱
    graph_data = build_graph(llm_result)

    # 6. 社区发现
    try:
        graph_data = add_community_to_graph(graph_data)
    except Exception as e:
        print("社区发现失败，保留默认group：", e)

    # 7. 中心性分析
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

    # 8. 写回节点大小
    graph_data = apply_analysis_to_graph(graph_data, analysis_result)

    return llm_result, graph_data, analysis_result

async def generate_graph_background(task_id: str, session_id: str = None):
    """
    后台生成图谱：
    开始分析后自动生成，但前端不主动显示。
    """
    cache = load_cache(task_id)
    if not cache:
        return

    if cache.get("graph") and cache.get("analysis") and cache.get("ai_result"):
        return

    try:
        cache["graph_status"] = "running"
        cache["graph_error"] = ""
        save_cache(task_id, cache)

        ocr_result = cache.get("ocr", {})
        extracted_text = (
            cache.get("text", "")
            or ocr_result.get("structured_text", "")
            or ocr_result.get("raw_text", "")
        )

        if not extracted_text.strip():
            cache["graph_status"] = "failed"
            cache["graph_error"] = "OCR结果为空，无法生成图谱"
            save_cache(task_id, cache)
            return

        llm_result = graph_deep_extract(extracted_text)

        llm_result, graph_data, analysis_result = build_full_graph_pipeline(llm_result)

        cache["ai_result"] = llm_result
        cache["graph"] = graph_data
        cache["analysis"] = analysis_result
        cache["graph_status"] = "done"
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
        "blocks": []
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

        extracted_text = (
            ocr_result.get("structured_text")
            or ocr_result.get("raw_text")
            or ""
        )

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

                    extracted_text = (
                        ocr_result.get("structured_text")
                        or ocr_result.get("raw_text")
                        or ""
                    )
                except Exception as e:
                    print("qwen-vl-plus版面重建失败，保留原OCR排版：", e)

    if text and text.strip():
        extracted_text = (extracted_text + "\n" + text).strip()

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
                "blocks": []
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
        "visual_detection": visual_detection
    }


@router.post("/upload/ai-summary")
async def ai_summary_after_ocr(task_id: str = Form(None)):
    """
    只做快速AI总结，不做实体关系抽取，不生成图谱。
    这样前端可以更快显示AI总结。
    """
    if not task_id:
        return {"success": False, "error": "缺少 task_id"}

    cache = load_cache(task_id)
    if not cache:
        return {"success": False, "error": "未找到OCR缓存，请重新上传"}

    extracted_text = cache.get("text", "")
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

    # AI总结返回后，后台自动开始生成图谱
    asyncio.create_task(generate_graph_background(task_id))

    return {
        "success": True,
        "task_id": task_id,
        "result": result
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

    # 1. 如果后台已经生成完成，直接返回，不重复生成
    if cache.get("graph") and cache.get("analysis") and cache.get("ai_result"):
        return {
            "success": True,
            "task_id": task_id,
            "status": "done",
            "llm": cache.get("ai_result"),
            "result": cache.get("ai_result"),
            "graph": cache.get("graph"),
            "analysis": cache.get("analysis")
        }

    # 2. 如果后台正在生成，前端提示等待
    if cache.get("graph_status") == "running":
        return {
            "success": True,
            "task_id": task_id,
            "status": "running",
            "message": "知识图谱正在生成中，请稍后再点击查看"
        }

    # 3. 如果还没有生成，点击时现场补生成一次
    try:
        cache["graph_status"] = "running"
        cache["graph_error"] = ""
        save_cache(task_id, cache)

        ocr_result = cache.get("ocr", {})
        extracted_text = (
            cache.get("text", "")
            or ocr_result.get("structured_text", "")
            or ocr_result.get("raw_text", "")
        )

        if not extracted_text.strip():
            cache["graph_status"] = "failed"
            cache["graph_error"] = "OCR结果为空，无法生成图谱"
            save_cache(task_id, cache)
            return {"success": False, "error": "OCR结果为空，无法生成图谱"}

        # 图谱阶段只读文本，不再走视觉模型/版面修复
        result = graph_deep_extract(extracted_text)

        llm_result, graph_data, analysis_result = build_full_graph_pipeline(result)

        cache["ai_result"] = llm_result
        cache["graph"] = graph_data
        cache["analysis"] = analysis_result
        cache["graph_status"] = "done"
        cache["graph_error"] = ""
        save_cache(task_id, cache)

    except Exception as e:
        print("图谱构建失败：", e)

        cache["graph_status"] = "failed"
        cache["graph_error"] = str(e)
        save_cache(task_id, cache)

        llm_result = {
            "summary": "",
            "entities": [],
            "relations": [],
            "keywords": []
        }

        graph_data = {
            "nodes": [],
            "edges": []
        }

        analysis_result = {
            "core_nodes": [],
            "important_paths": [],
            "metrics": {}
        }

        return {
            "success": False,
            "task_id": task_id,
            "status": "failed",
            "error": str(e),
            "llm": llm_result,
            "result": llm_result,
            "graph": graph_data,
            "analysis": analysis_result
        }

    # 4. 保存历史记录，保留
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
        "analysis": analysis_result
    }


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(None),
    text: str = Form(None),
    session_id: str = Form(None),
    background: BackgroundTasks = None
):
    """
    兼容旧前端的上传接口。
    """
    ocr_response = await upload_ocr_only(file=file, text=text)
    if not ocr_response.get("success"):
        return ocr_response

    task_id = ocr_response["task_id"]
    ai_response = await ai_summary_after_ocr(task_id=task_id)
    if not ai_response.get("success"):
        return ai_response

    try:
        asyncio.create_task(graph_after_summary(task_id=task_id, session_id=session_id))
    except Exception as e:
        print("启动后台图谱生成失败：", e)

    return {
        "success": True,
        "task_id": task_id,
        "text": ocr_response.get("text", ""),
        "ocr": ocr_response.get("ocr", {}),
        "result": ai_response.get("result", {}),
        "graph": None,
        "analysis": None,
        "message": "AI总结已生成，图谱生成已在后台启动。"
    }
