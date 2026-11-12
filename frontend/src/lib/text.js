// Turns the LLM answer into plain data blocks that React renders as text nodes.
// Nothing here produces HTML, so LLM output can never inject markup (XSS-safe).
// Supported: paragraphs, "- " / "• " / "1. " lists, **bold** and http(s) links.

import { safeHttpUrl } from './urls.js';

const INLINE = /(\*\*[^*]+\*\*|\bhttps?:\/\/[^\s<>()]+[^\s<>().,;:!?»"'])/g;

export function parseInline(text) {
  const parts = [];
  let last = 0;
  for (const m of text.matchAll(INLINE)) {
    if (m.index > last) parts.push({ type: 'text', text: text.slice(last, m.index) });
    const tok = m[0];
    if (tok.startsWith('**')) parts.push({ type: 'strong', text: tok.slice(2, -2) });
    else {
      const href = safeHttpUrl(tok);
      parts.push(href ? { type: 'link', text: tok, href } : { type: 'text', text: tok });
    }
    last = m.index + tok.length;
  }
  if (last < text.length) parts.push({ type: 'text', text: text.slice(last) });
  return parts;
}

const LIST_ITEM = /^\s*(?:[-•*]|\d+[.)])\s+/;

export function parseAnswer(answer) {
  const blocks = [];
  const lines = String(answer ?? '').replace(/\r\n/g, '\n').split('\n');
  let para = [];
  let list = null;

  const flushPara = () => {
    if (para.length) blocks.push({ type: 'p', parts: parseInline(para.join(' ')) });
    para = [];
  };
  const flushList = () => {
    if (list) blocks.push(list);
    list = null;
  };

  for (const raw of lines) {
    const line = raw.trim();
    if (!line) { flushPara(); flushList(); continue; }
    const heading = /^#{1,4}\s+(.*)$/.exec(line);
    if (heading) { flushPara(); flushList(); blocks.push({ type: 'p', parts: [{ type: 'strong', text: heading[1].replace(/\*\*/g, '') }] }); continue; }
    if (LIST_ITEM.test(line)) {
      flushPara();
      const ordered = /^\s*\d/.test(line);
      if (!list || list.ordered !== ordered) { flushList(); list = { type: ordered ? 'ol' : 'ul', ordered, items: [] }; }
      list.items.push(parseInline(line.replace(LIST_ITEM, '')));
    } else {
      flushList();
      para.push(line);
    }
  }
  flushPara();
  flushList();
  return blocks;
}
