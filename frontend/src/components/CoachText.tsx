// Shows a coach answer written in simple Markdown: paragraphs, "- " lists,
// "1. " lists, "## " headings and **bold**. Built from React elements (never
// raw HTML), so a text coming from the model can't inject anything in the page.
import type { ReactNode } from 'react'

/** "**bold** text" -> ["", <strong>bold</strong>, " text"]. */
function inline(text: string): ReactNode[] {
  return text
    .split(/\*\*(.+?)\*\*/g)
    .map((part, i) => (i % 2 ? <strong key={i}>{part}</strong> : part))
}

type Block = { kind: 'p'; text: string } | { kind: 'h'; text: string } | ListBlock
type ListBlock = { kind: 'ul' | 'ol'; items: string[] }

function blocks(text: string): Block[] {
  const result: Block[] = []
  for (const raw of text.split('\n')) {
    const line = raw.trim()
    const last = result.at(-1)
    const bullet = /^[-*•] (.*)/.exec(line)
    const numbered = /^\d+[.)] (.*)/.exec(line)
    if (!line) continue
    if (bullet || numbered) {
      const kind = bullet ? 'ul' : 'ol'
      const item = (bullet ?? numbered)![1]!
      if (last?.kind === kind) last.items.push(item)
      else result.push({ kind, items: [item] })
    } else if (line.startsWith('#')) {
      result.push({ kind: 'h', text: line.replace(/^#+\s*/, '') })
    } else {
      result.push({ kind: 'p', text: line })
    }
  }
  return result
}

export default function CoachText({ text }: { text: string }) {
  return (
    <>
      {blocks(text).map((block, i) => {
        if (block.kind === 'h') return <h3 key={i}>{inline(block.text)}</h3>
        if (block.kind === 'p') return <p key={i}>{inline(block.text)}</p>
        // A list: the tag is its kind ("ul" or "ol").
        const List = block.kind
        return (
          <List key={i}>
            {block.items.map((item, j) => (
              <li key={j}>{inline(item)}</li>
            ))}
          </List>
        )
      })}
    </>
  )
}
