import { createBrowserRouter, Navigate } from "react-router-dom";
import { AdminLayout } from "@/features/admin/AdminLayout";

// Les layouts Buyer et Seller sont purgés en Phase 01.
// Muntu Core se concentre sur les interfaces Guichet, Agent et Admin.

export const router = createBrowserRouter([
  { path: "/", element: <Navigate to="/admin" replace /> },
  { path: "/admin/*", element: <AdminLayout /> }
]);
