import { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import { reportDownload } from '../reportDownload'
import type { ResearchReport, ResearchState } from '../types'

type Tab = 'report' | 'plan' | 'sources'

function httpUrl(value: string | null): string | null {
  if (!value) return null
  try {
    const url = new URL(value)
    return url.protocol === 'https:' || url.protocol === 'http:' ? url.href : null
  } catch {
    return null
  }
}

function download(report: ResearchReport, format: 'markdown' | 'html') {
  const { filename, blob } = reportDownload(report, format)
  const href = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = href
  link.download = filename
  document.body.append(link)
  link.click()
  link.remove()
  window.setTimeout(() => URL.revokeObjectURL(href), 0)
}

export default function ReportView({ state }: { state: ResearchState }) {
  const [tab, setTab] = useState<Tab>('report')
  const report = state.report
  if (!report) return <p className="empty-result">没有可展示的报告。请重新发起研究。</p>

  return <div className="result-view">
    <div className="result-toolbar">
      <div role="tablist" aria-label="研究结果视图" className="result-tabs">
        {([['report', '报告'], ['plan', '研究计划'], ['sources', '来源']] as const).map(([name, label]) =>
          <button key={name} type="button" role="tab" aria-selected={tab === name} onClick={() => setTab(name)}>{label}</button>)}
      </div>
      <div className="download-actions">
        <button type="button" onClick={() => download(report, 'markdown')}>下载 Markdown</button>
        {report.html && <button type="button" onClick={() => download(report, 'html')}>下载 HTML</button>}
      </div>
    </div>
    {tab === 'report' && <article className="report-body">
      {!report.markdown.trimStart().startsWith(`# ${report.title}`) && <h1>{report.title}</h1>}
      <div className="report-markdown"><ReactMarkdown components={{ a: ({ href, children }) => {
        const safe = httpUrl(href ?? null)
        return safe ? <a href={safe} target="_blank" rel="noopener noreferrer">{children}</a> : <span>{children}</span>
      } }}>{report.markdown}</ReactMarkdown></div>
      <p className="report-caveat">引用编号存在不代表结论已被原文验证；重要结论请打开来源复核。</p>
    </article>}
    {tab === 'plan' && <div className="result-panel"><h2>研究计划</h2>
      {state.plan ? <ol className="plan-list">{state.plan.questions.map((question) => <li key={question.id}><span>{question.id}</span><div><p>{question.text}</p><small>第 {question.round_number} 轮</small></div></li>)}</ol> : <p>没有可展示的研究计划。</p>}
    </div>}
    {tab === 'sources' && <div className="result-panel"><h2>证据来源</h2>
      <p className="section-intro">共 {state.evidence.length} 条证据 · 仅展示本次任务返回的来源</p>
      <ol className="source-list">{state.evidence.map((source) => {
        const url = source.source_type === 'web' ? httpUrl(source.url) : null
        return <li key={source.source_id}><span className="source-id">{source.source_id}</span><div className="source-detail">
          <h3>{url ? <a href={url} target="_blank" rel="noopener noreferrer">{source.title}</a> : source.title}</h3>
          <p className="source-meta">{source.source_type === 'document' ? <>{source.document_name}{source.page_number ? ` · 第 ${source.page_number} 页` : ''}</> : (url ?? '网页来源')}</p>
          <p>{source.content}</p>
        </div></li>
      })}</ol>
    </div>}
    <footer className="result-footer">任务 {state.task_id} · 第 {state.round_number} 轮 · {state.usage.llm_requests} 次模型请求 · {state.usage.search_requests} 次检索请求</footer>
  </div>
}
