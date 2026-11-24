import useWebSocket from "react-use-websocket";

export function useSessionWebSocket(shopToken: string | undefined) {
  const protocol = location.protocol === "https:" ? "wss:" : "ws:";
  const url = shopToken ? `${protocol}//${location.host}/ws/session/${shopToken}/` : null;
  return useWebSocket(url ?? undefined, {
    shouldReconnect: () => true,
    reconnectAttempts: 10,
    reconnectInterval: (attempt) => Math.min(30_000, 1000 * 2 ** attempt),
    heartbeat: true,
  });
}
