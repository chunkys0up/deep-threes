import { useState, useRef, useEffect } from "react";
import { Send, Bot, Filter, X } from "lucide-react";

const API_BASE_URL = "http://localhost:8000";
const HISTORY_CAP = 20;
const GREETING = {
  id: "greeting",
  text: "Ready when you are. Ask anything about the film — possessions, shots, players.",
  sender: "bot",
  timestamp: new Date(),
};
const SUMMARY_PROMPT =
  "Give me a 2–3 sentence scouting-style summary of this clip. No highlight indices.";

// Module-level dedup — survives StrictMode's mount → unmount → remount so
// the auto-summary fires EXACTLY ONCE per unique video URL.
const SUMMARIZED_KEYS = new Set();

export default function Chatbot({
  timestamps = [],
  highlightFilter = null,
  setHighlightFilter,
  videoReadyKey = null,
}) {
  const [messages, setMessages] = useState([GREETING]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [rateLimited, setRateLimited] = useState(false);

  const messagesEndRef = useRef(null);
  const rateLimitTimerRef = useRef(null);
  const messagesRef = useRef(messages);
  messagesRef.current = messages;

  useEffect(() => () => clearTimeout(rateLimitTimerRef.current), []);

  const busy = sending || rateLimited;

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, sending]);

  // Shared send logic — used for both user-typed messages and the auto-summary.
  const sendMessage = async (messageText, { asUser = true } = {}) => {
    if (sending || rateLimited) return;
    if (asUser) {
      setMessages((prev) => [
        ...prev,
        {
          id: Date.now().toString(),
          text: messageText,
          sender: "user",
          timestamp: new Date(),
        },
      ]);
    }
    setSending(true);

    const history = messagesRef.current
      .slice(-HISTORY_CAP)
      .map((m) => ({ sender: m.sender, text: m.text }));

    try {
      const res = await fetch(`${API_BASE_URL}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: messageText, history }),
      });

      // DEBUG: 429 swallow disabled so rate-limit errors show in the chat log.
      // Re-enable this block to hide 429s behind the "Buffering…" status.
      // if (res.status === 429) {
      //   const body = await res.json().catch(() => ({}));
      //   const retryAfter = Math.max(
      //     5,
      //     Number(body?.detail?.retry_after) || 30,
      //   );
      //   setSending(false);
      //   setRateLimited(true);
      //   clearTimeout(rateLimitTimerRef.current);
      //   rateLimitTimerRef.current = setTimeout(() => {
      //     setRateLimited(false);
      //   }, retryAfter * 1000);
      //   return;
      // }

      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        const detailMsg =
          typeof data?.detail === "string"
            ? data.detail
            : data?.detail?.error || `Chat error ${res.status}`;
        throw new Error(detailMsg);
      }

      setMessages((prev) => [
        ...prev,
        {
          id: (Date.now() + 1).toString(),
          text: data.text || "(no response)",
          sender: "bot",
          timestamp: new Date(),
        },
      ]);

      if (Array.isArray(data.highlights) && data.highlights.length > 0) {
        setHighlightFilter?.(data.highlights);
      }
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          id: (Date.now() + 1).toString(),
          text: `⚠ ${err.message || "Could not reach the AI"}`,
          sender: "bot",
          timestamp: new Date(),
        },
      ]);
    } finally {
      setSending(false);
    }
  };

  // Auto-summary: fire EXACTLY ONCE per unique video URL.
  useEffect(() => {
    if (!videoReadyKey) {
      SUMMARIZED_KEYS.clear();
      return;
    }
    if (SUMMARIZED_KEYS.has(videoReadyKey)) return;
    if (sending || rateLimited) return;
    SUMMARIZED_KEYS.add(videoReadyKey);
    sendMessage(SUMMARY_PROMPT, { asUser: false });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [videoReadyKey, sending, rateLimited]);

  const handleSend = () => {
    const trimmed = input.trim();
    if (!trimmed || sending) return;
    setInput("");
    sendMessage(trimmed, { asUser: true });
  };

  const handleKeyPress = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const filterCount = highlightFilter?.length ?? 0;
  const totalCount = timestamps.length;

  return (
    <aside className="fixed right-0 top-0 h-full w-80 bg-[#0b1733]/90 backdrop-blur-md border-l border-[#1b3a6b] flex flex-col z-30 shadow-[0_0_40px_rgba(0,0,0,0.45)]">
      <header className="p-4 border-b border-[#1b3a6b] flex items-center gap-3">
        <div className="p-2 rounded-lg bg-[#4a8db8]/18 border border-[#4a8db8]/25">
          <Bot className="w-5 h-5 text-[#4a8db8]" />
        </div>
        <div className="leading-tight">
          <h2
            className="text-[#f4ecd8] font-medium tracking-tight"
            style={{ fontFamily: "var(--heading)", fontSize: "17px" }}
          >
            AI Assistant
          </h2>
          <p className="text-[#7a89a8] text-xs">
            {sending
              ? "Thinking…"
              : rateLimited
                ? "Buffering…"
                : "Always here to help"}
          </p>
        </div>
      </header>

      {highlightFilter && (
        <div className="px-4 py-2 border-b border-[#1b3a6b] bg-[rgba(74,141,184,0.08)] flex items-center gap-2 text-xs">
          <Filter className="w-3.5 h-3.5 text-[#4a8db8]" />
          <span className="text-[#f4ecd8] flex-1">
            Showing {filterCount} of {totalCount} events
          </span>
          <button
            type="button"
            onClick={() => setHighlightFilter?.(null)}
            className="flex items-center gap-1 text-[#7a89a8] hover:text-[#f4ecd8] transition-colors"
            title="Clear filter and show all events"
          >
            <X className="w-3.5 h-3.5" />
            Show all
          </button>
        </div>
      )}

      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {messages.map((message) => (
          <div
            key={message.id}
            className={`flex ${
              message.sender === "user" ? "justify-end" : "justify-start"
            }`}
          >
            <div
              className={`max-w-[82%] rounded-xl px-3.5 py-2.5 border ${
                message.sender === "user"
                  ? "bg-[rgba(217,164,65,0.12)] border-[rgba(217,164,65,0.35)] border-r-2 text-[#f4ecd8]"
                  : "bg-[rgba(74,141,184,0.10)] border-[rgba(74,141,184,0.25)] border-l-2 text-[#f4ecd8]"
              }`}
            >
              <p className="text-sm leading-snug whitespace-pre-wrap">
                {message.text}
              </p>
              <p className="text-[11px] text-[#7a89a8] mt-1">
                {message.timestamp.toLocaleTimeString([], {
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </p>
            </div>
          </div>
        ))}

        {sending && (
          <div className="flex justify-start">
            <div className="max-w-[82%] rounded-xl px-3.5 py-3 border bg-[rgba(74,141,184,0.10)] border-[rgba(74,141,184,0.25)] border-l-2">
              <div className="flex items-center gap-1.5">
                <span className="chat-typing-dot" />
                <span
                  className="chat-typing-dot"
                  style={{ animationDelay: "150ms" }}
                />
                <span
                  className="chat-typing-dot"
                  style={{ animationDelay: "300ms" }}
                />
              </div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <div className="p-4 border-t border-[#1b3a6b]">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={handleKeyPress}
            disabled={busy}
            placeholder={
              sending
                ? "Waiting for reply…"
                : rateLimited
                  ? "Buffering… please wait"
                  : "Ask about the film…"
            }
            className="flex-1 bg-[#0a1128] text-[#f4ecd8] placeholder-[#7a89a8] rounded-lg px-3.5 py-2.5 text-sm border border-[#1b3a6b] focus:outline-none focus:border-[#d9a441] focus:ring-2 focus:ring-[rgba(217,164,65,0.25)] transition-colors disabled:opacity-50"
          />
          <button
            onClick={handleSend}
            disabled={busy || !input.trim()}
            className="p-2.5 bg-[#d9a441] hover:bg-[#e8b757] text-[#0a1128] rounded-lg transition-colors shadow-[0_4px_16px_-4px_rgba(217,164,65,0.5)] disabled:opacity-50 disabled:cursor-not-allowed"
            aria-label="Send message"
          >
            <Send className="w-4 h-4" strokeWidth={2.2} />
          </button>
        </div>
      </div>
    </aside>
  );
}
