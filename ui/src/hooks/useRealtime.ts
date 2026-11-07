import { useEffect, useRef, useState } from "react";
import type { SocketEvent } from "../types";

export function useRealtime(onEvent: (event: SocketEvent) => void) {
  const callback = useRef(onEvent);
  const [connected, setConnected] = useState(false);
  callback.current = onEvent;

  useEffect(() => {
    let socket: WebSocket | null = null;
    let timer: number | undefined;
    let stopped = false;

    const connect = () => {
      if (stopped) return;
      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      socket = new WebSocket(protocol + "//" + window.location.host + "/ws");
      socket.onopen = () => setConnected(true);
      socket.onmessage = (message) => {
        try {
          callback.current(JSON.parse(message.data) as SocketEvent);
        } catch {
          // Keep the local stream alive if a malformed event is ever received.
        }
      };
      socket.onclose = () => {
        setConnected(false);
        if (!stopped) timer = window.setTimeout(connect, 2000);
      };
      socket.onerror = () => socket?.close();
    };

    connect();
    return () => {
      stopped = true;
      if (timer) window.clearTimeout(timer);
      socket?.close();
    };
  }, []);

  return connected;
}
