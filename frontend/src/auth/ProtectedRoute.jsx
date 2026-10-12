import { Navigate } from "react-router-dom";
import { useAuth } from "./AuthProvider";

export default function ProtectedRoute({ children }) {
  const { session, loading } = useAuth();
  if (loading) return <p className="p-10 text-center font-display text-gold">Invocando…</p>;
  return session ? children : <Navigate to="/login" replace />;
}
