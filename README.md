# AI-Graph-System

## 1. 项目简介
AI-Graph-System 是一个前后端分离的多模态信息解析与知识图谱构建系统。系统支持文件上传与文本输入，提供 OCR 识别、AI 语义抽取、图谱构建、图分析与可视化展示的完整链路。

本说明仅描述当前代码中已实现并已接入主流程的能力。

## 2. 技术栈（基于代码实证）

### 2.1 前端
- Vue 3
- Vite
- Vue Router
- Axios
- ECharts（graph + force 布局）

### 2.2 后端
- FastAPI
- Uvicorn
- python-multipart（文件/表单上传）
- NetworkX（图构建与图分析）
- PaddleOCR 2.7.3
- OpenCV
- PyMuPDF（PDF 渲染）
- LTP（候选实体与分词辅助）
- OpenAI SDK（DashScope 兼容模式调用 Qwen）

### 2.3 大模型接口
- qwen-plus：文本结构化抽取与总结
- qwen-vl-plus：图文场景（版面重建）

## 3. 系统架构与主流程

### 3.1 前后端交互
前端通过 REST API 调用后端，核心接口包括：
- `POST /upload/ocr-only`
- `POST /upload/ai-summary`
- `POST /upload/graph`
- `POST /analyze-text`
- `GET /history`

### 3.2 主流程（上传链路）
1. `ocr-only`：完成 OCR 与结构化文本组织，返回 `raw_text / structured_text / blocks`。
2. `ai-summary`：快速总结（不做图谱抽取），并触发后台图谱任务。
3. `graph`：返回图谱抽取、图构建、社区分组、多中心性分析结果。

## 4. OCR 分类处理流程

当前 OCR 不是单一路径调用，而是按输入类型分流：

### 4.1 文本输入
- 不走 OCR 引擎。
- 直接构造 `text_input` 结构化结果，写入 `raw_text / structured_text / blocks`。

### 4.2 图片输入
- 先进行图片边缘安全扩展。
- 先做“疑似表格”判定：
	- 若疑似表格，优先走 `PPStructure`。
	- 若失败或非表格，回退到普通 `PaddleOCR`。
- 普通 OCR 路径包含图像增强变体识别与结果融合（基于 IoU 去重）。
- 之后做 OCR 后处理与版面恢复，输出：
	- `raw_text`
	- `structured_text`
	- `blocks`
	- `modules`
	- `layout_type`

### 4.3 PDF 输入
- 使用 PyMuPDF 将 PDF 转为多页图片。
- 逐页复用图片 OCR 路径。
- 按页汇总文本与 block，并在 block 中记录页码。

### 4.4 PP-Structure 版本说明
- 项目依赖为 `paddleocr==2.7.3`。
- 当前代码调用 `PPStructure()`，未显式覆盖结构模型版本。
- 在当前安装包默认配置下，结构模型版本为 **PP-StructureV2**。

## 5. 语义抽取与图谱生成流程

图谱生成阶段主链路为：

1. `graph_deep_extract`（Qwen 抽取，结合 LTP 候选）
2. `refine_entity_types`（实体类型二次修正）
3. `semantic_merge_result`（语义去重合并）
4. 再次 `refine_entity_types`
5. `refine_llm_relations`（关系修正）
6. `build_graph`（NetworkX DiGraph 构建节点与边）
7. `add_community_to_graph`（社区划分）
8. `analyze_graph`（多中心性分析）
9. 写回节点 `importance/symbolSize` 用于前端渲染

## 6. 图分析算法（多中心性）

已接入并用于主流程：
- Degree Centrality
- Betweenness Centrality
- PageRank（按边权重计算）

融合策略：

`fusion = 0.3 * degree + 0.3 * betweenness + 0.4 * pagerank`

此外，系统还会在高分核心节点之间计算关键路径（shortest path），用于展示重要关系路径。

## 7. 可视化实现
- 使用 ECharts `graph` 系列 + `force` 布局。
- 节点按 `type/category` 分类着色。
- 边展示关系标签（`relation`）。
- 节点大小与后端融合重要性分数联动。

## 8. 数据与存储
- 后端缓存：`backend/storage/cache/*.json`
- 历史记录：`backend/storage/history.json`
- 前端状态：
	- `sessionStorage`：当前分析结果/当前图谱
	- `localStorage`：历史记录与会话 ID

## 9. 运行说明

### 9.1 后端
在 `backend` 目录执行：

```bash
python -m uvicorn main:app --reload
```

### 9.2 前端
在 `frontend` 目录执行：

```bash
npm install
npm run dev
```

## 10. 项目特点
- OCR 与输入处理采用分类分流（文本/图片/PDF）。
- OCR 输出为结构化三层结果，而非单一字符串。
- 图谱分析采用多中心性融合，支持核心节点与关键路径解释。
- 仅使用当前代码中已接入能力，不依赖未上线模块。
