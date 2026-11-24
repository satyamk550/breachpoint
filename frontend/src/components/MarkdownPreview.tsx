import DOMPurify from 'dompurify'

export function MarkdownPreview({ markdown, className = '' }: { markdown: string; className?: string }) {
  const safe = DOMPurify.sanitize(markdown, { USE_PROFILES: { html: true } })
  return <div className={`markdown-preview ${className}`.trim()} dangerouslySetInnerHTML={{ __html: safe.replace(/\n/g, '<br />') }} />
}
