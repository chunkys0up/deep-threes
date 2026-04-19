import { useState, useRef, useEffect } from "react";
import { Send, Bot } from "lucide-react";

export default function Chatbot() {
  const [messages, setMessages] = useState([
    {
      id: "1",
      text: "Ready when you are. Ask anything about the film — possessions, shots, players.",
      sender: "bot",
      timestamp: new Date(),
    },
  ]);
  const [input, setInput] = useState("");
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSend = () => {
    if (!input.trim()) return;

    const userMessage = {
      id: Date.now().toString(),
      text: input,
      sender: "user",
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput("");

    setTimeout(() => {
      const botMessage = {
        id: (Date.now() + 1).toString(),
        text: "I'm a demo assistant for now. Once the CV backend is wired in, I'll surface exact timestamps and player stats.",
        sender: "bot",
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, botMessage]);
    }, 1000);
  };

  const handleKeyPress = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <aside className="fixed right-0 top-0 h-full w-80 bg-[#0b1733]/90 backdrop-blur-md border-l border-[#1b3a6b] flex flex-col z-30 shadow-[0_0_40px_rgba(0,0,0,0.45)]">
      <header className="p-4 border-b border-[#1b3a6b] flex items-center gap-3">
        <div className="p-2 rounded-lg bg-[#4a8db8]/18 border border-[#4a8db8]/25">
          <Bot className="w-5 h-5 text-[#4a8db8]" />
        </div>
        <div className="leading-tight">
          <h2 className="text-[#f4ecd8] font-medium tracking-tight" style={{ fontFamily: 'var(--heading)', fontSize: '17px' }}>
            AI Assistant
          </h2>
          <p className="text-[#7a89a8] text-xs">Always here to help</p>
        </div>
      </header>

      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {messages.map((message) => (
          <div
            key={message.id}
            className={`flex ${message.sender === "user" ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-[82%] rounded-xl px-3.5 py-2.5 border ${
                message.sender === "user"
                  ? "bg-[rgba(217,164,65,0.12)] border-[rgba(217,164,65,0.35)] border-r-2 text-[#f4ecd8]"
                  : "bg-[rgba(74,141,184,0.10)] border-[rgba(74,141,184,0.25)] border-l-2 text-[#f4ecd8]"
              }`}
            >
              <p className="text-sm leading-snug">{message.text}</p>
              <p className="text-[11px] text-[#7a89a8] mt-1">
                {message.timestamp.toLocaleTimeString([], {
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </p>
            </div>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      <div className="p-4 border-t border-[#1b3a6b]">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="Ask about the film…"
            className="flex-1 bg-[#0a1128] text-[#f4ecd8] placeholder-[#7a89a8] rounded-lg px-3.5 py-2.5 text-sm border border-[#1b3a6b] focus:outline-none focus:border-[#d9a441] focus:ring-2 focus:ring-[rgba(217,164,65,0.25)] transition-colors"
          />
          <button
            onClick={handleSend}
            className="p-2.5 bg-[#d9a441] hover:bg-[#e8b757] text-[#0a1128] rounded-lg transition-colors shadow-[0_4px_16px_-4px_rgba(217,164,65,0.5)]"
            aria-label="Send message"
          >
            <Send className="w-4 h-4" strokeWidth={2.2} />
          </button>
        </div>
      </div>
    </aside>
  );
}
