import json
import os
from datetime import datetime
from utils.encoding_utils import read_text_auto

HISTORY_FILE = "storage/history.json"


# =====================
# 初始化文件
# =====================
def init_history():
    if not os.path.exists("storage"):
        os.makedirs("storage")

    if not os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f, ensure_ascii=False, indent=2)


# =====================
# 保存历史记录
# =====================
def save_history(session_id, data):
    init_history()

    history = json.loads(read_text_auto(HISTORY_FILE))

    if session_id not in history:
        history[session_id] = []

    history[session_id].append({
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "text": data.get("text"),
        "result": data.get("result"),
        "graph": data.get("graph")
    })

    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


# =====================
# 获取历史记录
# =====================
def get_history(session_id):
    init_history()

    history = json.loads(read_text_auto(HISTORY_FILE))

    return history.get(session_id, [])