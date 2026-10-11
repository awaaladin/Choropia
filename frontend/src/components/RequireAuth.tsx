import { Navigate, Outlet, useLocation } from "react-router";
import { useAuth } from "@/lib/auth";

/** Pages that need an account bounce to /login and return here after signing in. */
export function RequireAuth() {
  const { loggedIn } = useAuth();
  const location = useLocation();
  if (!loggedIn) {
    return <Navigate to={`/login?next=${encodeURIComponent(location.pathname + location.search)}`} replace />;
  }
  return <Outlet />;
}
