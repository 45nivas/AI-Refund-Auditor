import React, { useState, useEffect } from "react";
import axios from "axios";
import { useWebSocket } from "./hooks/useWebSocket";
import { useVoice } from "./hooks/useVoice";

import ChatPanel from "./components/ChatPanel";
import CustomerList from "./components/CustomerList";
import ReasoningLog from "./components/ReasoningLog";
import DecisionsTable from "./components/DecisionsTable";

import { Activity, CheckCircle2, XCircle, RotateCcw, AlertTriangle, Sun, Moon } from "lucide-react";

export default function App() {
  const [customers, setCustomers] = useState([]);
  const [decisions, setDecisions] = useState([]);
  const [selectedCustomerId, setSelectedCustomerId] = useState("");
  const [messages, setMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [sessionId, setSessionId] = useState("");
  
  // Theme state
  const [theme, setTheme] = useState(() => {
    return localStorage.getItem("theme") || "dark";
  });

  // Apply theme to document element
  useEffect(() => {
    localStorage.setItem("theme", theme);
    if (theme === "dark") {
      document.documentElement.classList.add("dark");
    } else {
      document.documentElement.classList.remove("dark");
    }
  }, [theme]);

  const toggleTheme = () => {
    setTheme((prev) => (prev === "dark" ? "light" : "dark"));
  };

  // Generate a new unique session ID
  const generateNewSession = () => {
    return `sess_${Math.random().toString(36).substring(2, 11)}`;
  };

  // Fetch initial data from port 8080
  const fetchData = async () => {
    try {
      const customersRes = await axios.get("http://localhost:8080/customers");
      setCustomers(customersRes.data);
      
      // Auto-select first customer as default
      if (customersRes.data.length > 0) {
        handleSelectCustomer(customersRes.data[0]);
      }
    } catch (err) {
      console.error("Error fetching customers:", err);
    }

    try {
      const decisionsRes = await axios.get("http://localhost:8080/admin/decisions");
      setDecisions(decisionsRes.data);
    } catch (err) {
      console.error("Error fetching decisions:", err);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  // Set up WebSocket connection for logs on port 8080
  const { logs, clearLogs, isConnected } = useWebSocket(sessionId);

  // Set up Voice transcript trigger
  const handleTranscript = (transcript) => {
    handleSendMessage(transcript);
  };

  const {
    voiceEnabled,
    setVoiceEnabled,
    isListening,
    isPlaying,
    startListening,
    stopListening,
    speakText,
    stopPlayback
  } = useVoice(handleTranscript);

  // Handle selecting a customer profile
  const handleSelectCustomer = (customer) => {
    setSelectedCustomerId(customer.customer_id);
    stopPlayback();
    
    // Clear chat and assign a brand new session (for clean websocket log feeds)
    setMessages([]);
    clearLogs();
    setSessionId(generateNewSession());
  };

  // Handle sending message to agent
  const handleSendMessage = async (text) => {
    if (!selectedCustomerId) {
      alert("Please select a customer profile first!");
      return;
    }

    // Append user message
    const userMsg = { sender: "user", text, timestamp: new Date() };
    setMessages((prev) => [...prev, userMsg]);
    setIsLoading(true);
    stopPlayback();

    try {
      const response = await axios.post("http://localhost:8080/chat", {
        customer_id: selectedCustomerId,
        message: text,
        session_id: sessionId,
      });

      // Append agent message
      const agentMsg = {
        sender: "agent",
        text: response.data.response,
        decision: response.data.decision,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, agentMsg]);

      // Play text to speech if enabled
      if (voiceEnabled) {
        speakText(response.data.response);
      }

      // Re-fetch decisions to sync dashboard history table
      const decisionsRes = await axios.get("http://localhost:8080/admin/decisions");
      setDecisions(decisionsRes.data);
      
    } catch (err) {
      console.error("Chat error:", err);
      const errMsg = {
        sender: "agent",
        text: `Error processing request: ${err.response?.data?.detail || err.message}`,
        decision: "DENY",
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errMsg]);
    } finally {
      setIsLoading(false);
    }
  };

  // Calculate live stats from decisions history
  const totalProcessed = decisions.length;
  const approvedCount = decisions.filter((d) => d.decision === "APPROVE").length;
  const deniedCount = decisions.filter((d) => d.decision === "DENY").length;
  const escalatedCount = decisions.filter((d) => d.decision === "ESCALATE").length;
  const partialCount = decisions.filter((d) => d.decision === "PARTIAL").length;

  return (
    <div className="h-screen bg-[var(--background)] text-[var(--text)] flex flex-col font-sans transition-colors duration-200 overflow-hidden">
      {/* Navbar */}
      <header className="h-16 border-b border-[var(--border)] bg-[var(--card)]/70 backdrop-blur-md px-6 flex justify-between items-center shrink-0 sticky top-0 z-50 transition-colors duration-200">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-[var(--accent)] flex items-center justify-center font-bold text-white shadow-lg shadow-blue-500/20">
            RA
          </div>
          <div>
            <h1 className="text-md font-bold tracking-tight text-[var(--text)]">Refund Auditor</h1>
            <p className="text-[10px] text-[var(--text-muted)] font-medium">Production AI Agent Operations Dashboard</p>
          </div>
          {/* Light/Dark Toggle */}
          <button
            onClick={toggleTheme}
            className="p-2 rounded-lg border border-[var(--border)] bg-[var(--card)] text-[var(--text-muted)] hover:text-[var(--text)] hover:bg-[var(--background)] transition-all ml-2"
            title={theme === "dark" ? "Switch to Light Theme" : "Switch to Dark Theme"}
          >
            {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
          </button>
        </div>

        <div className="flex items-center gap-3.5">
          {isConnected ? (
            <div className="flex items-center gap-1.5 text-xs text-green-500 bg-green-500/10 border border-green-500/25 px-2.5 py-1 rounded-full font-mono font-medium">
              <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse"></span>
              Agent Online
            </div>
          ) : (
            <div className="flex items-center gap-1.5 text-xs text-red-500 bg-red-500/10 border border-red-500/25 px-2.5 py-1 rounded-full font-mono font-medium">
              <span className="w-1.5 h-1.5 rounded-full bg-red-500"></span>
              Agent Offline
            </div>
          )}
        </div>
      </header>

      {/* Main Grid Workspace */}
      <main className="flex-1 grid grid-cols-1 lg:grid-cols-12 gap-6 p-6 max-w-[1600px] w-full mx-auto overflow-hidden">
        {/* Left: Chat Panel */}
        <section className="lg:col-span-5 h-full overflow-hidden">
          <ChatPanel
            messages={messages}
            customerId={selectedCustomerId}
            setCustomerId={(id) => {
              setSelectedCustomerId(id);
              const matched = customers.find((c) => c.customer_id === id);
              if (matched) {
                handleSelectCustomer(matched);
              }
            }}
            onSendMessage={handleSendMessage}
            isListening={isListening}
            isPlaying={isPlaying}
            startListening={startListening}
            stopListening={stopListening}
            isLoading={isLoading}
            voiceEnabled={voiceEnabled}
            setVoiceEnabled={setVoiceEnabled}
          />
        </section>

        {/* Right: Admin Panel */}
        <section className="lg:col-span-7 flex flex-col gap-6 h-full overflow-hidden">
          {/* Stats Cards */}
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-4 shrink-0">
            <div className="bg-[var(--card)] border border-[var(--border)] p-4 rounded-xl shadow-sm flex items-center gap-3 transition-colors duration-200">
              <div className="p-2.5 rounded-lg bg-[var(--accent-bg)] text-[var(--accent)]">
                <Activity size={18} />
              </div>
              <div>
                <p className="text-[10px] uppercase tracking-wider text-[var(--text-muted)] font-bold">Total Runs</p>
                <h3 className="text-lg font-bold text-[var(--text)] mt-0.5">{totalProcessed}</h3>
              </div>
            </div>

            <div className="bg-[var(--card)] border border-[var(--border)] p-4 rounded-xl shadow-sm flex items-center gap-3 transition-colors duration-200">
              <div className="p-2.5 rounded-lg bg-green-500/10 text-green-500">
                <CheckCircle2 size={18} />
              </div>
              <div>
                <p className="text-[10px] uppercase tracking-wider text-[var(--text-muted)] font-bold">Approved</p>
                <h3 className="text-lg font-bold text-[var(--text)] mt-0.5">{approvedCount}</h3>
              </div>
            </div>

            <div className="bg-[var(--card)] border border-[var(--border)] p-4 rounded-xl shadow-sm flex items-center gap-3 transition-colors duration-200">
              <div className="p-2.5 rounded-lg bg-red-500/10 text-red-500">
                <XCircle size={18} />
              </div>
              <div>
                <p className="text-[10px] uppercase tracking-wider text-[var(--text-muted)] font-bold">Denied</p>
                <h3 className="text-lg font-bold text-[var(--text)] mt-0.5">{deniedCount}</h3>
              </div>
            </div>

            <div className="bg-[var(--card)] border border-[var(--border)] p-4 rounded-xl shadow-sm flex items-center gap-3 transition-colors duration-200">
              <div className="p-2.5 rounded-lg bg-[var(--accent-bg)] text-[var(--accent)]">
                <RotateCcw size={18} />
              </div>
              <div>
                <p className="text-[10px] uppercase tracking-wider text-[var(--text-muted)] font-bold">Partial</p>
                <h3 className="text-lg font-bold text-[var(--text)] mt-0.5">{partialCount}</h3>
              </div>
            </div>

            <div className="bg-[var(--card)] border border-[var(--border)] p-4 rounded-xl shadow-sm col-span-2 sm:col-span-1 flex items-center gap-3 transition-colors duration-200">
              <div className="p-2.5 rounded-lg bg-yellow-500/10 text-yellow-500">
                <AlertTriangle size={18} />
              </div>
              <div>
                <p className="text-[10px] uppercase tracking-wider text-[var(--text-muted)] font-bold">Escalated</p>
                <h3 className="text-lg font-bold text-[var(--text)] mt-0.5">{escalatedCount}</h3>
              </div>
            </div>
          </div>

          {/* Middle Row: Customers and Logs */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 h-[40%] min-h-0 shrink-0">
            <CustomerList
              customers={customers}
              selectedCustomerId={selectedCustomerId}
              onSelectCustomer={handleSelectCustomer}
            />
            <ReasoningLog logs={logs} />
          </div>

          {/* Bottom Row: Decisions History Table */}
          <div className="flex-1 min-h-0">
            <DecisionsTable decisions={decisions} />
          </div>
        </section>
      </main>
    </div>
  );
}
