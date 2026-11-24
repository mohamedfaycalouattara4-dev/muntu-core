import { useEffect, useState } from "react";

export function DisputesPage() {
  const [disputes, setDisputes] = useState<any[]>([]);
  useEffect(() => {
    fetch("/api/v1/disputes/", { headers: { Authorization: `Bearer ${localStorage.token ?? ""}` } })
      .then((r) => r.json()).then(setDisputes);
  }, []);
  return (
    <div>
      <h2>Litiges en cours</h2>
      <ul>
        {disputes.map((d) => (
          <li key={d.id}>
            Commande {d.order_id} — <strong>{d.state}</strong> — {d.reason}
          </li>
        ))}
      </ul>
    </div>
  );
}
