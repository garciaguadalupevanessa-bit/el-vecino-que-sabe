import { useCallback, useState } from "react";
import { ApiError, sendChat, trimHistory } from "../lib/api.js";
import { cleanMessages } from "../lib/messages.js";
import { buildProfile, validateProfile } from "../lib/profile.js";
import { useLocalStorage } from "./useLocalStorage.js";

const NO_RESULTS = { aids: [], sources: [], trace: [], coverage_notes: [] };

export function useChat(profileValues) {
  const [messages, setMessages] = useLocalStorage("messages", [], cleanMessages);
  const [results, setResults] = useState(NO_RESULTS);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState(null);

  // Returns true if the message was sent and answered (so the UI can clear the text box)
  const send = useCallback(
    async (text) => {
      text = text.trim();
      if (!text || sending) return false;
      if (Object.keys(validateProfile(profileValues)).length) {
        setError("Revisa los datos marcados en el perfil antes de enviar.");
        return false;
      }

      const next = [...messages, { role: "user", content: text }];
      setError(null);
      setMessages(next);
      setSending(true);
      try {
        const r = await sendChat(trimHistory(next), buildProfile(profileValues));
        setMessages([...next, { role: "assistant", content: r.answer }]);
        setResults({ aids: r.aids, sources: r.sources, trace: r.trace, coverage_notes: r.coverage_notes });
        return true;
      } catch (e) {
        setMessages(messages); // undo the send so the user can retry with the same text
        setError(e instanceof ApiError ? e.message : "Ha ocurrido un error inesperado. Inténtalo de nuevo.");
        console.error(e);
        return false;
      } finally {
        setSending(false);
      }
    },
    [messages, sending, profileValues, setMessages],
  );

  const reset = useCallback(() => {
    if (sending) return;
    setMessages([]);
    setResults(NO_RESULTS);
    setError(null);
  }, [sending, setMessages]);

  return { messages, results, sending, error, send, reset };
}
