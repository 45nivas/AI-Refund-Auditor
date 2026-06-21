import React, { useState, useEffect, useRef } from "react";
import { Send, Mic, MicOff, User, Bot, Loader2, Volume2, VolumeX } from "lucide-react";

export default function ChatPanel({
  messages,
  customerId,
  setCustomerId,
  onSendMessage,
  isListening,
  isPlaying,
  startListening,
  stopListening,
  isLoading,
  voiceEnabled,
  setVoiceEnabled
}) {
  const [inputText, setInputText] = useState("");
  const messagesEndRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!inputText.trim() || isLoading) return;
    onSendMessage(inputText.trim());
    setInputText("");
  };

  const getDecisionBadge = (decision) => {
    if (!decision) return null;
    switch (decision) {
      case "APPROVE":
        return <span className="inline-flex items-center gap-1 text-[10px] bg-green-500/10 text-green-500 border border-green-500/20 px-2 py-0.5 rounded-full font-bold ml-2">APPROVED ✅</span>;
      case "DENY":
        return <span className="inline-flex items-center gap-1 text-[10px] bg-red-500/10 text-red-500 border border-red-500/20 px-2 py-0.5 rounded-full font-bold ml-2">DENIED ❌</span>;
      case "ESCALATE":
        return <span className="inline-flex items-center gap-1 text-[10px] bg-yellow-500/10 text-yellow-500 border border-yellow-500/20 px-2 py-0.5 rounded-full font-bold ml-2">ESCALATED ⚠️</span>;
      case "PARTIAL":
        return <span className="inline-flex items-center gap-1 text-[10px] bg-blue-500/10 text-blue-500 border border-blue-500/20 px-2 py-0.5 rounded-full font-bold ml-2">PARTIAL 🔄</span>;
      default:
        return null;
    }
  };

  return (
    <div className="flex flex-col h-full bg-[var(--card)] rounded-xl border border-[var(--border)] overflow-hidden shadow-lg transition-all duration-200">
      {/* Header */}
      <div className="p-4 border-b border-[var(--border)] bg-[var(--card)]/50 flex flex-wrap justify-between items-center gap-3 transition-colors duration-200">
        <div className="flex items-center gap-2">
          <div className="p-2 bg-[var(--accent-bg)] text-[var(--accent)] rounded-lg">
            <Bot size={20} />
          </div>
          <div>
            <h1 className="text-sm font-bold text-[var(--text)]">E-Store Support Agent</h1>
            <p className="text-[10px] text-[var(--text-muted)] font-medium">Automated Audit & Refund Processor</p>
          </div>
        </div>
        
        <div className="flex items-center gap-3">
          {/* Customer ID input */}
          <div className="flex items-center gap-1.5">
            <label className="text-xs font-bold text-[var(--text-muted)] font-mono">CUST:</label>
            <input
              type="text"
              value={customerId}
              onChange={(e) => setCustomerId(e.target.value.toUpperCase())}
              placeholder="e.g. CUST001"
              className="bg-[var(--background)] text-xs font-mono font-bold text-[var(--accent)] border border-[var(--border)] px-2.5 py-1.5 rounded-lg w-28 focus:outline-none focus:border-[var(--accent)] text-center transition-colors duration-200"
            />
          </div>

          {/* Voice Mode Toggle */}
          <button
            onClick={() => setVoiceEnabled(!voiceEnabled)}
            className={`p-2 rounded-lg border transition-all flex items-center gap-1 text-xs font-semibold ${
              voiceEnabled
                ? "bg-[var(--accent-bg)] border-[var(--accent)] text-[var(--accent)]"
                : "bg-[var(--background)] border-[var(--border)] text-[var(--text-muted)] hover:text-[var(--text)]"
            }`}
            title={voiceEnabled ? "Mute Voice Outputs" : "Read Responses Aloud"}
          >
            {voiceEnabled ? <Volume2 size={16} /> : <VolumeX size={16} />}
            <span className="hidden sm:inline">Voice</span>
          </button>
        </div>
      </div>

      {/* Chat Area */}
      <div className="flex-1 p-4 overflow-y-auto space-y-4 no-scrollbar bg-[var(--background)]/10 transition-colors duration-200">
        {messages.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-center p-6 space-y-3">
            <Bot size={44} className="text-[var(--text-muted)] animate-pulse" />
            <div className="max-w-xs">
              <h3 className="text-sm font-bold text-[var(--text)]">Start Refund Request</h3>
              <p className="text-xs text-[var(--text-muted)] mt-1 leading-relaxed">
                Select a profile from the active customers list on the right, or type a Customer ID. Then explain what you need.
              </p>
            </div>
          </div>
        ) : (
          messages.map((m, index) => {
            const isUser = m.sender === "user";
            return (
              <div
                key={index}
                className={`flex gap-3 max-w-[85%] ${
                  isUser ? "ml-auto flex-row-reverse" : "mr-auto"
                }`}
              >
                {/* Avatar */}
                <div
                  className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 shadow-sm transition-all duration-200 ${
                    isUser ? "bg-[var(--accent)] text-white" : "bg-[var(--accent-bg)] text-[var(--accent)]"
                  }`}
                >
                  {isUser ? <User size={16} /> : <Bot size={16} />}
                </div>

                {/* Bubble */}
                <div className="space-y-1">
                  <div
                    className={`p-3.5 rounded-2xl leading-relaxed text-sm transition-all duration-200 ${
                      isUser
                        ? "bg-[var(--accent)] text-white rounded-tr-none shadow-md shadow-blue-500/10"
                        : "bg-[var(--card)] text-[var(--text)] rounded-tl-none border border-[var(--border)] shadow-sm"
                    }`}
                  >
                    {m.text}
                  </div>
                  {!isUser && m.decision && (
                    <div className="flex items-center mt-1">
                      {getDecisionBadge(m.decision)}
                    </div>
                  )}
                </div>
              </div>
            );
          })
        )}
        
        {/* Loading Spinner */}
        {isLoading && (
          <div className="flex gap-3 mr-auto max-w-[80%]">
            <div className="w-8 h-8 rounded-lg flex items-center justify-center bg-[var(--accent-bg)] text-[var(--accent)] shrink-0">
              <Bot size={16} />
            </div>
            <div className="bg-[var(--card)] text-[var(--text-muted)] p-3.5 rounded-2xl rounded-tl-none border border-[var(--border)] flex items-center gap-2 shadow-sm">
              <Loader2 size={16} className="animate-spin text-[var(--accent)]" />
              <span className="text-xs font-medium">Agent evaluating refund policy...</span>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Waveform visualizer */}
      {(isListening || isPlaying) && (
        <div className="bg-[var(--card)]/90 border-t border-[var(--border)] px-4 py-2 flex items-center justify-between gap-3 animate-fade-in-up transition-colors duration-200">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-red-500 animate-ping"></span>
            <span className="text-xs font-bold text-[var(--text-muted)] font-mono">
              {isListening ? "LISTENING (STT)" : "SPEAKING (TTS)"}
            </span>
          </div>
          {/* Bouncing audio wave bars */}
          <div className="flex items-center gap-1 h-5 pr-2">
            <div className="w-0.5 bg-[var(--accent)] rounded animate-bounce h-3 [animation-duration:0.6s]"></div>
            <div className="w-0.5 bg-[var(--accent)] rounded animate-bounce h-5 [animation-duration:0.4s] [animation-delay:0.15s]"></div>
            <div className="w-0.5 bg-[var(--accent)] rounded animate-bounce h-2 [animation-duration:0.5s] [animation-delay:0.3s]"></div>
            <div className="w-0.5 bg-[var(--accent)] rounded animate-bounce h-4 [animation-duration:0.7s] [animation-delay:0.05s]"></div>
            <div className="w-0.5 bg-[var(--accent)] rounded animate-bounce h-3 [animation-duration:0.55s] [animation-delay:0.2s]"></div>
          </div>
        </div>
      )}

      {/* Input Form */}
      <form onSubmit={handleSubmit} className="p-4 bg-[var(--card)] border-t border-[var(--border)] flex items-center gap-3 transition-colors duration-200">
        {/* Mic control */}
        <button
          type="button"
          onClick={isListening ? stopListening : startListening}
          className={`p-3 rounded-lg border transition-all relative ${
            isListening
              ? "bg-red-500/20 border-red-500 text-red-500 scale-105 shadow-lg shadow-red-500/20 animate-[pulse_1.5s_infinite]"
              : "bg-[var(--background)] border-[var(--border)] text-[var(--text-muted)] hover:text-[var(--text)] hover:scale-105 active:scale-95"
          }`}
          title={isListening ? "Stop Voice Input" : "Speak Message"}
        >
          {isListening && (
            <span className="absolute -inset-px rounded-lg bg-red-500/20 animate-ping opacity-75"></span>
          )}
          <span className="relative z-10 flex items-center justify-center">
            {isListening ? <MicOff size={18} /> : <Mic size={18} />}
          </span>
        </button>

        {/* Text Input */}
        <input
          type="text"
          value={inputText}
          onChange={(e) => setInputText(e.target.value)}
          placeholder={isListening ? "Listening... Speak your request" : "Explain refund request or ask policy questions..."}
          disabled={isLoading || isListening}
          className="flex-1 bg-[var(--background)] border border-[var(--border)] rounded-lg px-4 py-3 text-sm focus:outline-none focus:border-[var(--accent)] text-[var(--text)] placeholder-[var(--text-muted)] disabled:opacity-50 transition-colors duration-200"
        />

        {/* Send Button */}
        <button
          type="submit"
          disabled={isLoading || !inputText.trim() || isListening}
          className="bg-[var(--accent)] hover:bg-[var(--accent-hover)] text-white p-3 rounded-lg transition-all shadow-sm disabled:opacity-50 disabled:hover:bg-[var(--accent)]"
        >
          <Send size={18} />
        </button>
      </form>
    </div>
  );
}
