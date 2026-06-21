import React from "react";

export default function CustomerList({ customers, selectedCustomerId, onSelectCustomer }) {
  return (
    <div className="flex flex-col h-full bg-[var(--card)] rounded-xl border border-[var(--border)] overflow-hidden shadow-sm transition-all duration-200">
      <div className="p-4 border-b border-[var(--border)] bg-[var(--card)]/50 flex justify-between items-center transition-colors duration-200">
        <h2 className="text-xs font-bold tracking-wider text-[var(--text-muted)] uppercase">Active Profiles</h2>
        <span className="text-xs bg-[var(--background)] text-[var(--text)] font-mono px-2 py-0.5 rounded-full border border-[var(--border)] transition-colors duration-200">
          {customers.length} Loaded
        </span>
      </div>
      <div className="flex-1 overflow-y-auto divide-y divide-[var(--border)] no-scrollbar transition-colors duration-200">
        {customers.map((c) => {
          const isSelected = c.customer_id === selectedCustomerId;
          return (
            <button
              key={c.customer_id}
              onClick={() => onSelectCustomer(c)}
              className={`w-full text-left p-3.5 transition-all flex justify-between items-center outline-none ${
                isSelected
                  ? "bg-[var(--accent-bg)] border-l-4 border-[var(--accent)]"
                  : "hover:bg-[var(--background)] border-l-4 border-transparent"
              }`}
            >
              <div className="flex-1 min-w-0 pr-3">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-mono font-bold text-[var(--accent)] bg-[var(--accent-bg)] px-1.5 py-0.2 rounded border border-[var(--accent)]/10">
                    {c.customer_id}
                  </span>
                  <span className="text-sm font-semibold text-[var(--text)] truncate">{c.name}</span>
                </div>
                <div className="text-xs text-[var(--text-muted)] mt-1 truncate">
                  {c.product_name} • <span className="font-mono text-[var(--text)] font-medium">₹{c.order_amount.toLocaleString("en-IN")}</span>
                </div>
              </div>
              
              <div className="flex flex-col items-end justify-center gap-1.5 shrink-0">
                <span className={`text-[10px] uppercase tracking-wider px-2 py-0.5 rounded font-bold ${
                  c.delivery_status === "delivered" ? "bg-green-500/10 text-green-500 border border-green-500/20" :
                  c.delivery_status === "in_transit" ? "bg-yellow-500/10 text-yellow-500 border border-yellow-500/20" :
                  "bg-red-500/10 text-red-500 border border-red-500/20"
                }`}>
                  {c.delivery_status.replace("_", " ")}
                </span>
                
                <span className="text-[10px] font-mono text-[var(--text-muted)]">
                  Refunds: <strong className={c.previous_refund_count >= 3 ? "text-red-500 font-bold" : "text-[var(--text)]"}>{c.previous_refund_count}</strong>/3
                </span>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
