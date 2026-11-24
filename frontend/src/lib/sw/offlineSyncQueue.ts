/**
 * OfflineSyncQueue — IndexedDB pour actions critiques (OTP validation, mission update).
 * Conformité V2 §11.4 (PWA offline-first).
 */
import { openDB, IDBPDatabase } from "idb";

interface QueuedAction {
  id: string;
  endpoint: string;
  method: "POST" | "PATCH" | "DELETE";
  body: any;
  created_at: number;
  attempts: number;
}

let dbPromise: Promise<IDBPDatabase> | null = null;

async function getDb() {
  if (!dbPromise) {
    dbPromise = openDB("kalyce-offline", 1, {
      upgrade(db) {
        db.createObjectStore("queue", { keyPath: "id" });
      }
    });
  }
  return dbPromise;
}

export async function enqueue(action: Omit<QueuedAction, "id" | "created_at" | "attempts">) {
  const db = await getDb();
  const item: QueuedAction = {
    id: crypto.randomUUID(),
    created_at: Date.now(),
    attempts: 0,
    ...action
  };
  await db.put("queue", item);
}

export async function flush(): Promise<number> {
  const db = await getDb();
  const all: QueuedAction[] = await db.getAll("queue");
  let sent = 0;
  for (const item of all) {
    try {
      const r = await fetch(item.endpoint, {
        method: item.method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(item.body)
      });
      if (r.ok) {
        await db.delete("queue", item.id);
        sent++;
      }
    } catch { /* keep */ }
  }
  return sent;
}
