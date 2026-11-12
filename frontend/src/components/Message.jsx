import { useMemo } from "react";
import { APP_NAME } from "../lib/brand.js";
import { textToHtml } from "../lib/markdown.js";

// The assistant's answer is escaped in textToHtml before being rendered (no XSS).
export default function Message({ role, content }) {
  const html = useMemo(() => (role === "assistant" ? textToHtml(content) : null), [role, content]);
  return (
    <article className={`message message-${role}`}>
      <span className="author">{role === "user" ? "Tú" : APP_NAME}</span>
      {html !== null ? (
        <div className="message-text" dangerouslySetInnerHTML={{ __html: html }} />
      ) : (
        <div className="message-text">{content}</div>
      )}
    </article>
  );
}
