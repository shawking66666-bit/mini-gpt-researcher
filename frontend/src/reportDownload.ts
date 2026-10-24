import type { ResearchReport } from './types'

export function reportDownload(report: ResearchReport, format: 'markdown' | 'html') {
  const markdown = format === 'markdown'
  return {
    filename: markdown ? 'task-report.md' : 'task-report.html',
    blob: new Blob([markdown ? report.markdown : report.html ?? ''], {
      type: markdown ? 'text/markdown;charset=utf-8' : 'text/html;charset=utf-8',
    }),
  }
}
