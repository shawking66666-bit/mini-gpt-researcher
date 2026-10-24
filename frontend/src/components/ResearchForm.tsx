import { formatFileSize } from '../formValidation'

type Phase = 'idle' | 'uploading' | 'researching' | 'completed' | 'failed'
type Props = {
  topic: string
  files: File[]
  phase: Phase
  onTopicChange: (value: string) => void
  onFilesChange: (files: File[]) => void
  onSubmit: () => void
}
export default function ResearchForm({ topic, files, phase, onTopicChange, onFilesChange, onSubmit }: Props) {
  const busy = phase === 'uploading' || phase === 'researching'
  return <form onSubmit={(event) => { event.preventDefault(); onSubmit() }} noValidate>
    <h2>新建研究</h2>
    <label htmlFor="research-topic">研究主题</label>
    <textarea id="research-topic" value={topic} onChange={(event) => onTopicChange(event.target.value)} placeholder="例如：分析某行业的发展趋势，并结合上传资料给出结论" rows={6} disabled={busy} />
    <label htmlFor="research-files">参考资料</label>
    <p className="field-hint">选择 1–5 个 PDF 或 Markdown；单文件 10 MiB，总计 30 MiB。</p>
    <input id="research-files" type="file" multiple accept=".pdf,.md,application/pdf,text/markdown" onChange={(event) => onFilesChange(Array.from(event.target.files ?? []))} disabled={busy} />
    {files.length > 0 && <ul className="selected-files">{files.map((file, index) => <li key={`${file.name}-${index}`}><span>{file.name}</span><small>{formatFileSize(file.size)}</small></li>)}</ul>}
    <button type="submit" disabled={busy}>{phase === 'uploading' ? '正在上传资料…' : phase === 'researching' ? '正在研究…' : '开始混合研究'}</button>
  </form>
}
