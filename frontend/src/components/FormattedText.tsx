import type { ReactNode } from 'react'

/** Renders **bold** segments inside a line. */
function renderInline(text: string): ReactNode[] {
  return text.split(/(\*\*[^*]+\*\*)/g).map((part, i) =>
    part.startsWith('**') && part.endsWith('**') && part.length > 4 ? (
      <strong key={i} className="font-semibold text-slate-900">
        {part.slice(2, -2)}
      </strong>
    ) : (
      part
    ),
  )
}

type Block =
  | { kind: 'p'; lines: string[] }
  | { kind: 'ul'; items: string[] }
  | { kind: 'ol'; items: string[] }
  | { kind: 'h'; text: string }

function parse(text: string): Block[] {
  const blocks: Block[] = []
  for (const raw of text.split(/\r?\n/)) {
    const line = raw.trimEnd()
    const last = blocks[blocks.length - 1]
    const bullet = /^\s*[-*•]\s+(.*)$/.exec(line)
    const numbered = /^\s*\d+[.)]\s+(.*)$/.exec(line)
    const heading = /^#{1,6}\s+(.*)$/.exec(line)

    if (!line.trim()) {
      blocks.push({ kind: 'p', lines: [] })
    } else if (heading) {
      blocks.push({ kind: 'h', text: heading[1] })
    } else if (bullet) {
      if (last?.kind === 'ul') last.items.push(bullet[1])
      else blocks.push({ kind: 'ul', items: [bullet[1]] })
    } else if (numbered) {
      if (last?.kind === 'ol') last.items.push(numbered[1])
      else blocks.push({ kind: 'ol', items: [numbered[1]] })
    } else if (last?.kind === 'p' && last.lines.length > 0) {
      last.lines.push(line)
    } else {
      blocks.push({ kind: 'p', lines: [line] })
    }
  }
  return blocks.filter((b) => !(b.kind === 'p' && b.lines.length === 0))
}

/** Minimal markdown-ish renderer: paragraphs, line breaks, bullets, numbered lists, headings, bold. */
export function FormattedText({ text }: { text: string }) {
  const blocks = parse(text)
  return (
    <div className="space-y-2 text-sm leading-relaxed text-slate-700">
      {blocks.map((b, i) => {
        if (b.kind === 'h') return <p key={i} className="font-semibold text-slate-900">{renderInline(b.text)}</p>
        if (b.kind === 'ul')
          return (
            <ul key={i} className="list-disc space-y-1 pl-5">
              {b.items.map((item, j) => <li key={j}>{renderInline(item)}</li>)}
            </ul>
          )
        if (b.kind === 'ol')
          return (
            <ol key={i} className="list-decimal space-y-1 pl-5">
              {b.items.map((item, j) => <li key={j}>{renderInline(item)}</li>)}
            </ol>
          )
        return (
          <p key={i}>
            {b.lines.map((l, j) => (
              <span key={j}>
                {j > 0 && <br />}
                {renderInline(l)}
              </span>
            ))}
          </p>
        )
      })}
    </div>
  )
}
