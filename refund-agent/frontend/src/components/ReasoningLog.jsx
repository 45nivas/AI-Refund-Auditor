import React, { useEffect, useRef } from "react";

export default function ReasoningLog({ logs }) {
  const endRef = useRef(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  const getTagStyle = (tag, text) => {
    switch (tag) {
      case "TOOL":
        return "bg-blue-500/10 text-blue-500 border border-blue-500/20";
      case "CHECK":
        return "bg-yellow-500/10 text-yellow-500 border border-yellow-500/20";
      case "DECISION":
        if (text && (text.includes("DENY") || text.includes("ESCALATE"))) {
          return "bg-red-500/10 text-red-500 border border-red-500/20";
        }
        return "bg-emerald-500/10 text-emerald-500 border border-emerald-500/20";
      case "RESPONSE":
        return "bg-purple-500/10 text-purple-500 border border-purple-500/20";
      case "ERROR":
        return "bg-red-500/10 text-red-600 border border-red-500/20 font-bold";
      case "FALLBACK":
        return "bg-amber-500/15 text-amber-600 dark:text-amber-400 border border-amber-500/30 font-bold animate-pulse";
      default:
        return "bg-gray-500/10 text-gray-500 border border-gray-500/20";
    }
  };

  return (
    <div className="flex flex-col h-full bg-[var(--card)] rounded-xl border border-[var(--border)] overflow-hidden shadow-sm transition-all duration-200">
      <div className="p-4 border-b border-[var(--border)] bg-[var(--card)]/50 flex justify-between items-center transition-colors duration-200">
        <h2 className="text-xs font-bold tracking-wider text-[var(--text-muted)] uppercase">Agent Reasoning Log</h2>
        <span className="flex items-center gap-1.5 text-xs text-[var(--accent)] font-semibold">
          <span className="w-1.5 h-1.5 rounded-full bg-[var(--accent)] animate-pulse"></span>
          Live Stream
        </span>
      </div>
      
      <div className="flex-1 p-4 overflow-y-auto font-mono text-xs space-y-3.5 bg-[var(--background)]/50 no-scrollbar transition-colors duration-200">
        {logs.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-[var(--text-muted)] italic space-y-2">
            <span>Waiting for refund request to trigger agent...</span>
            <span className="text-[10px] opacity-75">Select a customer profile and send a message.</span>
          </div>
        ) : (
          logs.map((log, index) => (
            <div key={index} className="animate-fade-in-up flex gap-3 items-start">
              <span className={`px-2 py-0.5 rounded text-[10px] font-bold shrink-0 tracking-wider ${getTagStyle(log.tag, log.text)}`}>
                {log.tag}
              </span>
              <span className="text-[var(--text)] leading-relaxed break-words flex-1">
                {log.text}
              </span>
            </div>
          ))
        )}
        <div ref={endRef} />
      </div>
    </div>
  );
}
