import { Routes, Route } from "react-router-dom";
import { KycPage } from "./KycPage";
import { DisputesPage } from "./DisputesPage";
import { LedgerPage } from "./LedgerPage";
import { FreezePage } from "./FreezePage";

/**
 * Back-office opérateur — V2 §5.3 :
 *   KYC, litiges/quorum, ledger (finance), global freeze (admin only).
 */
export function AdminLayout() {
  return (
    <Routes>
      <Route path="kyc" element={<KycPage />} />
      <Route path="disputes" element={<DisputesPage />} />
      <Route path="finance/ledger" element={<LedgerPage />} />
      <Route path="freeze" element={<FreezePage />} />
    </Routes>
  );
}
