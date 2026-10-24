import { useRef, useState } from 'react'
import { createHybridResearch, uploadKnowledgeBase } from './api'
import ResearchForm, { validateInput } from './components/ResearchForm'
import type { ResearchState } from './types'
import './styles.css'

type Phase = 'idle' | 'uploading' | 'researching' | 'completed' | 'failed'

export default function App() {
  const [topic, setTopic] = useState('')
  const [files, setFiles] = useState<File[]>([])
  const [phase, setPhase] = useState<Phase>('idle')
  const [error, setError] = useState('')
  const [result, setResult] = useState<ResearchState | null>(null)
  const busy = useRef(false)

  async function submit() {
    if (busy.current) return
    const problem = validateInput(topic, files)
    if (problem) {
      setError(problem)
      setPhase('failed')
      return
    }
    busy.current = true
    setError('')
    setResult(null)
    setPhase('uploading')
    try {
      const knowledge = await uploadKnowledgeBase(files)
      if (knowledge.status !== 'ready' || !knowledge.knowledge_base_id) {
        throw new Error('资料库未就绪，请检查文件内容后重试。')
      }
      setPhase('researching')
      const state = await createHybridResearch(topic.trim(), knowledge.knowledge_base_id)
      if (state.status !== 'completed') {
        throw new Error('研究失败，请检查服务状态或修改主题后重试。')
      }
      if (!state.report) throw new Error('研究已结束，但未生成报告，请稍后重试。')
      setResult(state)
      setPhase('completed')
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '操作失败，请稍后重试。')
      setPhase('failed')
    } finally {
      busy.current = false
    }
  }

  return <div className="app-shell">
    <header className="app-header"><span className="brand">Mini GPT Researcher</span><span className="header-note">本地运行 · 单用户模式</span></header>
    <main className="workspace">
      <aside className="workspace-aside">
        <ResearchForm topic={topic} files={files} phase={phase} onTopicChange={setTopic} onFilesChange={setFiles} onSubmit={submit} />
        {error && <p role="alert" className="feedback error">{error}</p>}
        {phase === 'uploading' && <p role="status" className="feedback">正在上传资料，请稍候…</p>}
        {phase === 'researching' && <p role="status" className="feedback">正在研究，请稍候。当前接口会在完成后一次返回结果。</p>}
      </aside>
      <section className="workspace-main" aria-label="研究结果">
        {result?.report ? <h1>{result.report.title}</h1> : <div className="empty-view"><h1>让资料与网页一起回答问题</h1><p>填写研究主题并选择 PDF 或 Markdown，生成可追溯来源的研究报告。</p></div>}
      </section>
    </main>
  </div>
}
