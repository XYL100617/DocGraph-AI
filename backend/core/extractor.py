from core.ocr import image_to_text
from core.llm import analyze_text
from graph.build import build_graph
from utils.file_manager import save_file
from utils.image_preprocess import preprocess_image
import asyncio

async def process_pipeline(file):
    # 1. 保存图片
    path = save_file(file)
    
    processed_path = preprocess_image(path)
    # 2. OCR
    text = image_to_text(processed_path)

    # 3. LLM分析
    result = analyze_text(text)

    # 4. 图谱构建
    graph = build_graph(result)

    return {
        "text": text,
        "result": result,
        "graph": graph
    }

def fallback_analyze_text(text: str):
    text = (text or "").strip()

    if not text:
        return {
            "summary": "",
            "entities": [],
            "relations": [],
            "keywords": []
        }

    # 短句兜底
    if len(text) <= 40:
        return {
            "summary": f"文本表达了“{text}”的核心思想。",
            "entities": [
                {
                    "name": text,
                    "type": "对象",
                    "description": "由短文本自动生成的主题节点"
                }
            ],
            "relations": [],
            "keywords": [text]
        }

    # 原来的 fallback 逻辑继续放下面