// Filters the stored history: only messages with a valid role and text.
export function cleanMessages(stored) {
  if (!Array.isArray(stored)) return [];
  return stored.filter(
    (m) => ["user", "assistant"].includes(m?.role) && typeof m.content === "string" && m.content.trim() !== "",
  );
}
