import os
import json
import base64
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"

load_dotenv(dotenv_path=ENV_PATH, override=True)

QWEN_API_KEY = os.getenv("QWEN_API_KEY")
QWEN_BASE_URL = os.getenv(
    "QWEN_BASE_URL",
    "https://dashscope.aliyuncs.com/compatible-mode/v1"
)

QWEN_TEXT_MODEL = os.getenv("QWEN_TEXT_MODEL", "qwen-plus")
QWEN_VL_MODEL = os.getenv("QWEN_VL_MODEL", "qwen-vl-plus")


def get_client():
    if not QWEN_API_KEY:
        raise RuntimeError("未配置 QWEN_API_KEY，请检查 backend/.env")

    return OpenAI(
        api_key=QWEN_API_KEY,
        base_url=QWEN_BASE_URL
    )


def extract_json_from_text(text: str):
    if not text:
        return None

    try:
        return json.loads(text)
    except Exception:
        pass

    start = text.find("{")
    end = text.rfind("}")

    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except Exception:
            return None

    return None


def image_to_base64(image_path: str):
    suffix = Path(image_path).suffix.lower()

    if suffix in [".jpg", ".jpeg"]:
        mime = "image/jpeg"
    elif suffix == ".png":
        mime = "image/png"
    else:
        mime = "image/jpeg"

    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")

    return f"data:{mime};base64,{b64}"


def call_text_llm(prompt: str) -> str:
    """
    调用 qwen-plus 文本模型。
    """

    client = get_client()

    response = client.chat.completions.create(
        model=QWEN_TEXT_MODEL,
        messages=[
            {
                "role": "system",
                "content": "你是一个严格输出JSON的中文信息结构化助手。"
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0.1
    )

    return response.choices[0].message.content


def call_vl_llm(prompt: str, image_path: str) -> str:
    """
    调用 qwen-vl-plus 图文模型。
    """

    client = get_client()
    image_url = image_to_base64(image_path)

    response = client.chat.completions.create(
        model=QWEN_VL_MODEL,
        messages=[
            {
                "role": "system",
                "content": "你是一个严格输出JSON的图文信息分析助手。"
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": prompt
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": image_url
                        }
                    }
                ]
            }
        ],
        temperature=0.1
    )

    return response.choices[0].message.content


def call_llm_json(prompt: str, fallback=None, image_path: str = None):
    """
    统一 JSON 调用入口。
    image_path 为空 → qwen-plus
    image_path 不为空 → qwen-vl-plus
    """

    try:
        if image_path:
            content = call_vl_llm(prompt, image_path)
        else:
            content = call_text_llm(prompt)

        data = extract_json_from_text(content)

        if data is not None:
            return data

        print("千问返回不是合法JSON：", content)

    except Exception as e:
        print("千问调用失败：", e)

    if fallback is not None:
        return fallback

    return {}

def call_summary_json(text: str):
    """
    快速AI总结：只总结，不抽实体关系。
    比完整图谱抽取快很多。
    """
    prompt = f"""
你是一个中文信息总结助手。

任务：只对下面文本生成简洁总结，不要抽取实体关系，不要生成知识图谱。

要求：
1. 只输出JSON。
2. 不要输出解释。
3. summary 不超过120字。
4. 如果是普通短句，就按普通语义总结，不要强行拔高。
5. 如果是诗句、歌词、名言，再概括其意象、情绪或思想。

输出格式：
{{
  "summary": "总结内容",
  "text_type": "普通行为句/名言格言/诗句歌词/标题短语/技术说明/文档内容/其他"
}}

文本：
{text}
"""

    fallback = {
        "summary": text[:120],
        "text_type": "其他"
    }

    return call_llm_json(prompt, fallback=fallback)

def call_summary_json(text: str):
    """
    快速AI总结：只总结，不抽实体关系，不生成知识图谱。
    """
    text = text or ""

    prompt = f"""
你是一个中文信息总结助手。

任务：只对下面文本生成简洁总结，不要抽取实体关系，不要生成知识图谱。

要求：
1. 只输出JSON。
2. 不要输出解释。
3. summary 不超过120字。
4. 如果是普通短句，就按普通语义总结，不要强行拔高。
5. 如果是诗句、歌词、名言，再概括其意象、情绪或思想。

输出格式：
{{
  "summary": "总结内容",
  "text_type": "普通行为句/名言格言/诗句歌词/标题短语/技术说明/文档内容/其他"
}}

文本：
{text}
"""

    fallback = {
        "summary": text[:120],
        "text_type": "其他"
    }

    return call_llm_json(prompt, fallback=fallback)