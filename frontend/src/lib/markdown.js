// Minimal and SAFE renderer for the assistant's answer: it escapes all HTML first and only then applies
// bold, code, links, lists and headings.
const ESCAPES = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };

export function escapeHtml(text) {
  return String(text ?? "").replace(/[&<>"']/g, (c) => ESCAPES[c]);
}

function link(url, text) {
  return `<a href="${url}" target="_blank" rel="noopener noreferrer">${text}</a>`;
}

function inline(escaped) {
  const stash = [];
  const keep = (html) => `\u0000${stash.push(html) - 1}\u0000`;

  const out = escaped
    // [text](https://...) with text and URL already escaped
    .replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, (_, text, url) => keep(link(url, text)))
    // <https://...> autolinks (the angle brackets arrive already escaped)
    .replace(/&lt;(https?:\/\/[^\s]+?)&gt;/g, (_, url) => keep(link(url, url)))
    // bare URLs
    .replace(/https?:\/\/[^\s<]*[^\s<.,;:!?)\]]/g, (url) => keep(link(url, url)))
    .replace(/`([^`]+)`/g, (_, c) => keep(`<code>${c}</code>`))
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");

  return out.replace(/\u0000(\d+)\u0000/g, (_, i) => stash[Number(i)]);
}

export function textToHtml(text) {
  const lines = String(text ?? "").replace(/\r/g, "").split("\n");
  const out = [];
  let list = null;
  let paragraph = [];

  const closeParagraph = () => {
    if (paragraph.length) out.push(`<p>${paragraph.join("<br>")}</p>`);
    paragraph = [];
  };
  const closeList = () => {
    if (list) out.push(`</${list}>`);
    list = null;
  };
  const openList = (type) => {
    closeParagraph();
    if (list !== type) {
      closeList();
      out.push(`<${type}>`);
      list = type;
    }
  };

  for (const raw of lines) {
    const line = escapeHtml(raw.trim());
    if (!line) {
      closeParagraph();
      closeList();
      continue;
    }
    let m;
    if ((m = line.match(/^[-*•]\s+(.*)$/))) {
      openList("ul");
      out.push(`<li>${inline(m[1])}</li>`);
    } else if ((m = line.match(/^\d+[.)]\s+(.*)$/))) {
      openList("ol");
      out.push(`<li>${inline(m[1])}</li>`);
    } else if ((m = line.match(/^#{1,4}\s+(.*)$/))) {
      closeParagraph();
      closeList();
      out.push(`<h4>${inline(m[1])}</h4>`);
    } else {
      closeList();
      paragraph.push(inline(line));
    }
  }
  closeParagraph();
  closeList();
  return out.join("");
}
