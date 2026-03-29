import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

const WsContext = createContext(null);

function wsUrl() {
  if (window.location.protocol === "file:") {
    return "ws://127.0.0.1:8756/ws";
  }
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${window.location.host}/ws`;
}

export function WsProvider({ children }) {
  const [connected, setConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState(null);
  const [logLines, setLogLines] = useState([]);
  const [gpu, setGpu] = useState(null);
  const wsRef = useRef(null);
  const reconnectRef = useRef(0);

  const pushLog = useCallback((line) => {
    setLogLines((prev) => [...prev.slice(-400), line]);
  }, []);

  useEffect(() => {
    let closed = false;

    function connect() {
      if (closed) return;
      const ws = new WebSocket(wsUrl());
      wsRef.current = ws;

      ws.onopen = () => {
        setConnected(true);
        reconnectRef.current = 0;
        try {
          ws.send(JSON.stringify({ command: "ping" }));
        } catch {
          /* ignore */
        }
      };

      ws.onclose = () => {
        setConnected(false);
        wsRef.current = null;
        if (closed) return;
        const delay = Math.min(1000 * 2 ** reconnectRef.current, 30000);
        reconnectRef.current += 1;
        setTimeout(connect, delay);
      };

      ws.onmessage = (ev) => {
        try {
          const data = JSON.parse(ev.data);
          setLastMessage(data);
          if (data.type === "log" && data.message) {
            pushLog(data.message);
          }
          if (data.type === "gpu" && data.gpu_util != null) {
            setGpu({
              gpu_util: data.gpu_util,
              mem_used_mb: data.mem_used_mb,
              mem_total_mb: data.mem_total_mb,
            });
          }
        } catch {
          /* ignore */
        }
      };
    }

    connect();
    return () => {
      closed = true;
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [pushLog]);

  const send = useCallback((obj) => {
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(obj));
    }
  }, []);

  const clearLogs = useCallback(() => setLogLines([]), []);

  const value = useMemo(
    () => ({
      connected,
      lastMessage,
      logLines,
      gpu,
      send,
      clearLogs,
    }),
    [connected, lastMessage, logLines, gpu, send, clearLogs]
  );

  return <WsContext.Provider value={value}>{children}</WsContext.Provider>;
}

export function useWs() {
  const ctx = useContext(WsContext);
  if (!ctx) throw new Error("useWs requires WsProvider");
  return ctx;
}
