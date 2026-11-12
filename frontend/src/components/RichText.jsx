import { parseAnswer } from '../lib/text.js';

// Renders LLM text as React text nodes only (never dangerouslySetInnerHTML).
function Inline({ parts }) {
  return parts.map((p, i) => {
    if (p.type === 'strong') return <strong key={i}>{p.text}</strong>;
    if (p.type === 'link') {
      return (
        <a key={i} href={p.href} target="_blank" rel="noopener noreferrer">
          {p.text}<span className="visually-hidden"> (se abre en una pestaña nueva)</span>
        </a>
      );
    }
    return <span key={i}>{p.text}</span>;
  });
}

export default function RichText({ text }) {
  return parseAnswer(text).map((b, i) => {
    if (b.type === 'ul' || b.type === 'ol') {
      const Tag = b.type;
      return <Tag key={i}>{b.items.map((parts, j) => <li key={j}><Inline parts={parts} /></li>)}</Tag>;
    }
    return <p key={i}><Inline parts={b.parts} /></p>;
  });
}
