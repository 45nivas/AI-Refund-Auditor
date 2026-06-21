import React from "react";

export default function DecisionsTable({ decisions }) {
  const getBadgeStyle = (decision) => {
    switch (decision) {
      case "APPROVE":
        return "bg-green-500/10 text-green-500 border border-green-500/20";
      case "DENY":
        return "bg-red-500/10 text-red-500 border border-red-500/20";
      case "ESCALATE":
        return "bg-yellow-500/10 text-yellow-500 border border-yellow-500/20";
      case "PARTIAL":
        return "bg-blue-500/10 text-blue-500 border border-blue-500/20";
      default:
        return "bg-gray-500/10 text-gray-500 border border-gray-500/20";
    }
  };

  const getBadgeIcon = (decision) => {
    switch (decision) {
      case "APPROVE": return "✅";
      case "DENY": return "❌";
      case "ESCALATE": return "⚠️";
      case "PARTIAL": return "🔄";
      default: return "";
    }
  };

  const formatTimestamp = (ts) => {
    if (!ts) return "";
    try {
      const date = new Date(ts.replace(" ", "T"));
      return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
    } catch (e) {
      return ts;
    }
  };

  return (
    <div className="flex flex-col h-full bg-[var(--card)] rounded-xl border border-[var(--border)] overflow-hidden shadow-sm transition-all duration-200">
      <div className="p-4 border-b border-[var(--border)] bg-[var(--card)]/50 transition-colors duration-200">
        <h2 className="text-xs font-bold tracking-wider text-[var(--text-muted)] uppercase">Audit Decisions History</h2>
      </div>
      <div className="flex-1 overflow-auto no-scrollbar transition-colors duration-200">
        {decisions.length === 0 ? (
          <div className="h-full flex items-center justify-center text-[var(--text-muted)] italic text-xs">
            No decisions logged yet. Execute a chat request to record one.
          </div>
        ) : (
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-[var(--border)] bg-[var(--background)]/20 text-[10px] uppercase tracking-wider text-[var(--text-muted)] font-bold transition-colors duration-200">
                <th className="p-3.5 pl-4">Customer</th>
                <th className="p-3.5">Name</th>
                <th className="p-3.5">Status</th>
                <th className="p-3.5">Policy Details / Citations</th>
                <th className="p-3.5 text-right pr-4">Timestamp</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border)] text-xs transition-colors duration-200">
              {decisions.map((d) => (
                <tr key={d.id} className="hover:bg-[var(--background)] transition-colors">
                  <td className="p-3 pl-4 font-mono font-bold text-[var(--accent)]">
                    {d.customer_id}
                  </td>
                  <td className="p-3 font-semibold text-[var(--text)]">
                    {d.name}
                  </td>
                  <td className="p-3">
                    <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[10px] font-bold tracking-wider ${getBadgeStyle(d.decision)}`}>
                      {d.decision} {getBadgeIcon(d.decision)}
                    </span>
                  </td>
                  <td className="p-3 text-[var(--text-muted)] max-w-[320px] truncate" title={d.reason}>
                    {d.reason}
                  </td>
                  <td className="p-3 text-right pr-4 text-[var(--text-muted)] font-mono">
                    {formatTimestamp(d.timestamp)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
