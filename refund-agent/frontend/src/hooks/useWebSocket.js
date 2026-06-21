import { useEffect, useState, useRef } from "react";

export function useWebSocket(sessionId) {
  const [logs, setLogs] = useState([]);
  const [isConnected, setIsConnected] = useState(false);
  const wsRef = useRef(null);

  useEffect(() => {
    if (!sessionId) return;

    // Clear logs when session changes
    setLogs([]);

    const wsProtocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsHost = "localhost:8080";
    const wsUrl = `${wsProtocol}//${wsHost}/ws/${sessionId}`;
    
    let reconnectTimeout;

    const connect = () => {
      console.log(`Connecting to WebSocket: ${wsUrl}`);
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        console.log("WebSocket connection established");
        setIsConnected(true);
      };

      ws.onmessage = (event) => {
        try {
          const logEntry = JSON.parse(event.data);
          setLogs((prevLogs) => {
            // Prevent duplicates by checking timestamp and text
            const isDuplicate = prevLogs.some(
              (l) => l.timestamp === logEntry.timestamp && l.text === logEntry.text
            );
            if (isDuplicate) return prevLogs;
            return [...prevLogs, logEntry];
          });
        } catch (err) {
          console.error("Failed to parse WebSocket message:", err);
        }
      };

      ws.onclose = () => {
        console.log("WebSocket connection closed, retrying in 3 seconds...");
        setIsConnected(false);
        reconnectTimeout = setTimeout(connect, 3000);
      };

      ws.onerror = (error) => {
        console.error("WebSocket error:", error);
        setIsConnected(false);
        ws.close();
      };
    };

    connect();

    return () => {
      clearTimeout(reconnectTimeout);
      if (wsRef.current && (wsRef.current.readyState === WebSocket.OPEN || wsRef.current.readyState === WebSocket.CONNECTING)) {
        wsRef.current.close();
      }
    };
  }, [sessionId]);

  const clearLogs = () => setLogs([]);

  return { logs, setLogs, isConnected, clearLogs };
}
