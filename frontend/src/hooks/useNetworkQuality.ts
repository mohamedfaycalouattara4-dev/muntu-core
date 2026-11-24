import { useEffect, useState } from "react";

export type NetworkQuality = "online" | "offline" | "2g" | "3g" | "4g";

export function useNetworkQuality(): NetworkQuality {
  const [quality, setQuality] = useState<NetworkQuality>("online");
  useEffect(() => {
    function update() {
      const conn = (navigator as any).connection;
      if (!navigator.onLine) return setQuality("offline");
      if (conn?.effectiveType === "2g") return setQuality("2g");
      if (conn?.effectiveType === "3g") return setQuality("3g");
      setQuality("online");
    }
    update();
    window.addEventListener("online", update);
    window.addEventListener("offline", update);
    return () => {
      window.removeEventListener("online", update);
      window.removeEventListener("offline", update);
    };
  }, []);
  return quality;
}
