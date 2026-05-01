<script setup>
import { useRouter } from "vue-router"

const router = useRouter()

const abilities = [
  { num: "01", title: "多模态输入", desc: "支持图片、PDF、文本等多源信息统一接入" },
  { num: "02", title: "结构化解析", desc: "融合 PaddleOCR 与 PP-StructureV2，识别标题、段落与表格结构" },
  { num: "03", title: "ECLA版面增强", desc: "对复杂版面进行结构修复与语义组织，提升后续抽取质量" },
  { num: "04", title: "AI语义理解", desc: "基于大模型生成摘要、关键词，并完成实体关系抽取" },
  { num: "05", title: "知识图谱构建", desc: "将非结构化内容转化为实体关系网络，实现知识结构化表达" },
  { num: "06", title: "图谱分析计算", desc: "结合 NetworkX 与多中心性融合，分析核心节点与关键路径" }
]
</script>

<template>
  <div class="about-page">
    <header class="about-header">
      <div class="brand">
        <div class="logo">AI</div>
        <div>
          <h1>关于项目</h1>
          <p>多模态AI信息解析与知识图谱生成系统</p>
        </div>
      </div>

      <div class="nav-actions">
        <button @click="router.push('/main')">返回主页</button>
        <button class="primary" @click="router.push('/history')">历史记录</button>
      </div>
    </header>

    <section class="hero-card">
      <div>
        <span class="badge">AI · OCR · PP-StructureV2 · Knowledge Graph</span>
        <h2>面向课堂场景的非结构化信息认知解析平台</h2>
        <p>
          本系统面向课堂资料、图片文档、PDF 与文本内容，围绕“识别、理解、抽取、建图、分析、展示”
          构建完整处理流程。系统通过 OCR 与结构化解析提取基础信息，再结合大模型语义理解和知识图谱分析，
          将分散的非结构化内容转化为可理解、可检索、可分析的结构化知识。
        </p>
      </div>

      <div class="hero-metrics">
        <div><b>6</b><span>核心能力</span></div>
        <div><b>KG</b><span>图谱建模</span></div>
        <div><b>AI</b><span>语义增强</span></div>
      </div>
    </section>

    <main class="about-grid">
      <section class="panel wide">
        <div class="panel-title"><span>1</span> 项目定位</div>
        <p>
          项目重点解决课堂与文档场景中“内容可见但难以结构化理解”的问题。
          系统不仅完成文字识别，还进一步结合 PP-StructureV2 文档结构化解析、ECLA 版面增强、
          大模型语义抽取与图谱分析计算，实现从非结构化信息到结构化知识网络的自动转换。
        </p>
      </section>

      <section class="panel">
        <div class="panel-title"><span>2</span> 技术路线</div>
        <div class="flow">
          <div>多模态输入</div>
          <b>→</b>
          <div>OCR/结构解析</div>
          <b>→</b>
          <div>AI语义分析</div>
          <b>→</b>
          <div>实体关系抽取</div>
          <b>→</b>
          <div>图谱分析展示</div>
        </div>
      </section>

      <section class="panel">
        <div class="panel-title"><span>3</span> 技术特点</div>
        <ul class="tech-list">
          <li>PaddleOCR + PP-StructureV2 文档结构化解析</li>
          <li>ECLA 版面增强与结构化文本优化</li>
          <li>大模型驱动的实体关系抽取与图谱增强总结</li>
          <li>NetworkX 多中心性融合与关键路径分析</li>
          <li>前后端分离与异步图谱生成，提高系统交互效率</li>
        </ul>
      </section>

      <section class="panel abilities-panel">
        <div class="panel-title"><span>4</span> 核心能力</div>
        <div class="ability-grid">
          <article v-for="item in abilities" :key="item.num" class="ability-card">
            <strong>{{ item.num }}</strong>
            <h3>{{ item.title }}</h3>
            <p>{{ item.desc }}</p>
          </article>
        </div>
      </section>

      <section class="panel">
        <div class="panel-title"><span>5</span> 创新亮点</div>
        <p>
          系统采用“快速AI总结 + 图谱增强AI总结”的双层分析结构：快速总结用于即时理解内容，
          图谱增强总结则结合实体关系、核心节点与图结构信息，生成更具解释性的深度分析结果。
        </p>
      </section>

      <section class="panel">
        <div class="panel-title"><span>6</span> 应用价值</div>
        <p>
          系统可用于课堂资料理解、学习笔记结构化、知识点梳理、文档内容分析与知识图谱展示，
          为后续学习路径推荐、知识检索、智能问答与课堂知识管理提供基础。
        </p>
      </section>
    </main>
  </div>
</template>

<style scoped>
.about-page {
  min-height: 100vh;
  background: var(--bg-main);
  color: var(--text-main);
  padding: 14px;
  box-sizing: border-box;
}

.about-header {
  height: 58px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border: 1px solid var(--border);
  background: var(--bg-header);
  border-radius: 14px;
  padding: 0 18px;
  box-shadow: 0 0 22px rgba(0, 94, 255, 0.14);
}

.brand {
  display: flex;
  align-items: center;
  gap: 12px;
}

.logo {
  width: 40px;
  height: 40px;
  border-radius: 14px;
  display: grid;
  place-items: center;
  font-weight: 800;
  color: #eaf6ff;
  background: linear-gradient(135deg, #0b63ce, #06152a);
  box-shadow: 0 0 18px rgba(59, 130, 246, 0.6);
}

.brand h1 {
  margin: 0;
  font-size: 20px;
}

.brand p {
  margin: 3px 0 0;
  color: var(--text-sub);
  font-size: 12px;
}

.nav-actions {
  display: flex;
  gap: 10px;
}

.nav-actions button {
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 8px 14px;
  background: var(--button-bg);
  color: var(--text-main);
  cursor: pointer;
}

.nav-actions .primary,
.nav-actions button:hover {
  background: linear-gradient(135deg, #0d7cff, #005ec9);
  color: white;
}

.hero-card {
  margin-top: 12px;
  display: grid;
  grid-template-columns: 1fr 320px;
  gap: 16px;
  border: 1px solid var(--border);
  background: var(--bg-card);
  border-radius: 16px;
  padding: 22px;
  box-shadow: inset 0 0 28px rgba(20, 95, 190, 0.08);
}

.badge {
  display: inline-block;
  color: #45e6a9;
  border: 1px solid rgba(69, 230, 169, 0.28);
  background: rgba(69, 230, 169, 0.08);
  border-radius: 999px;
  padding: 5px 10px;
  font-size: 12px;
}

.hero-card h2 {
  margin: 14px 0 10px;
  font-size: 26px;
  color: var(--text-main);
}

.hero-card p,
.panel p {
  margin: 0;
  color: var(--text-sub);
  line-height: 1.75;
  font-size: 14px;
}

.hero-metrics {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 9px;
  align-content: center;
}

.hero-metrics div {
  height: 96px;
  border-radius: 14px;
  display: grid;
  place-items: center;
  background: var(--bg-box);
  border: 1px solid var(--border);
}

.hero-metrics b {
  color: #45e6a9;
  font-size: 28px;
}

.hero-metrics span {
  color: var(--text-sub);
  font-size: 12px;
}

.about-grid {
  margin-top: 12px;
  display: grid;
  grid-template-columns: 1.2fr 1fr;
  gap: 12px;
}

.panel {
  border: 1px solid var(--border);
  background: var(--bg-card);
  border-radius: 14px;
  padding: 16px;
  box-shadow: inset 0 0 22px rgba(20, 95, 190, 0.08);
}

.panel.wide,
.abilities-panel {
  grid-column: 1 / -1;
}

.panel-title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
  font-weight: 700;
  color: var(--text-main);
}

.panel-title span {
  width: 24px;
  height: 24px;
  border-radius: 8px;
  display: grid;
  place-items: center;
  color: white;
  background: linear-gradient(135deg, #2d8cff, #7457ff);
}

.flow {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.flow div {
  padding: 8px 10px;
  border-radius: 10px;
  color: var(--text-main);
  background: var(--bg-box);
  border: 1px solid var(--border);
  font-size: 13px;
}

.flow b {
  color: #68a9ff;
}

.tech-list {
  margin: 0;
  padding-left: 18px;
  color: var(--text-sub);
  line-height: 1.85;
  font-size: 14px;
}

.ability-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 11px;
}

.ability-card {
  border: 1px solid var(--border);
  background: var(--bg-box);
  border-radius: 13px;
  padding: 14px;
}

.ability-card strong {
  color: #45e6a9;
  font-size: 12px;
}

.ability-card h3 {
  margin: 8px 0 6px;
  font-size: 15px;
  color: var(--text-main);
}

.ability-card p {
  font-size: 12.5px;
  line-height: 1.6;
  color: var(--text-sub);
}

@media (max-width: 1000px) {
  .hero-card,
  .about-grid {
    grid-template-columns: 1fr;
  }

  .ability-grid {
    grid-template-columns: 1fr;
  }

  .about-header {
    height: auto;
    padding: 12px;
    gap: 10px;
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>