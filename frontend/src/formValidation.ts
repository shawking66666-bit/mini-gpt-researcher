const MIB = 1024 * 1024

export function formatFileSize(bytes: number): string {
  return bytes < MIB ? `${(bytes / 1024).toFixed(1)} KiB` : `${(bytes / MIB).toFixed(1)} MiB`
}

export function validateInput(topic: string, files: File[]): string | null {
  if (!topic.trim()) return '请输入研究主题。'
  if (files.length === 0) return '请至少选择 1 个 PDF 或 Markdown 文件。'
  if (files.length > 5) return '一次最多选择 5 个文件。'
  if (files.some((file) => !/\.(pdf|md)$/i.test(file.name))) return '仅支持 PDF 或 Markdown（.md）文件。'
  if (files.some((file) => file.size > 10 * MIB)) return '单个文件不能超过 10 MiB。'
  if (files.reduce((sum, file) => sum + file.size, 0) > 30 * MIB) return '文件总大小不能超过 30 MiB。'
  return null
}
