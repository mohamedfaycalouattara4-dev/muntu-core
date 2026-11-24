import { useState } from "react";

/**
 * Bouton d'urgence : gel global. Requiert Admin + WebAuthn récent.
 */
export function FreezePage() {
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  return (
    <div className="freeze">
      <h2>Gel global d'urgence</h2>
      <p>Action irréversible. Réservée aux administrateurs titulaires de YubiKey.</p>
      <button
        onClick={async () => {
          const assertion = await requestWebAuthnAssertion();
          if (!assertion) {
            setError("Assertion WebAuthn échouée.");
            return;
          }
          const r = await fetch("/api/v1/admin/freeze/", {
            method: "POST",
            headers: {
              "Authorization": `Bearer ${localStorage.token ?? ""}`,
              "X-Webauthn-Assertion": JSON.stringify(assertion)
            }
          });
          if (r.ok) setStatus("Plateforme gelée.");
          else setError(`Erreur ${r.status}`);
        }}
      >
        Geler l'ensemble de la plateforme
      </button>
      {status && <p className="success">{status}</p>}
      {error && <p className="error">{error}</p>}
    </div>
  );
}

async function requestWebAuthnAssertion(): Promise<any | null> {
  if (!window.PublicKeyCredential) return null;
  const challenge = crypto.getRandomValues(new Uint8Array(32));
  try {
    const cred = await navigator.credentials.get({
      publicKey: { challenge, allowCredentials: [], userVerification: "required" }
    } as any);
    return { id: cred?.id, type: cred?.type, raw: cred?.toJSON?.() };
  } catch {
    return null;
  }
}
