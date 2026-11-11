import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, isAuthenticated, tokens } from "./api";
import { usePrefs } from "./prefs";
import type { User } from "./types";

/** `twoFactorRequired: true` means login() didn't complete — call verifyTwoFactor(challenge,
 * code) with the returned challenge to finish. */
type LoginResult = { twoFactorRequired: false } | { twoFactorRequired: true; challenge: string };

interface AuthContext {
  user: User | null;
  loggedIn: boolean;
  loading: boolean;
  login: (identifier: string, password: string) => Promise<LoginResult>;
  loginWithGoogle: (idToken: string) => Promise<LoginResult>;
  verifyTwoFactor: (challenge: string, code: string) => Promise<void>;
  register: (payload: Record<string, string>) => Promise<void>;
  logout: () => Promise<void>;
}

const Ctx = createContext<AuthContext | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const prefs = usePrefs();
  const [loggedIn, setLoggedIn] = useState(isAuthenticated());

  const me = useQuery({
    queryKey: ["me"],
    queryFn: api.me,
    enabled: loggedIn,
    staleTime: 5 * 60_000,
    retry: false,
  });

  // An expired session (refresh failed → tokens cleared) drops us back to logged-out.
  useEffect(() => {
    if (me.isError && !tokens.access) setLoggedIn(false);
  }, [me.isError]);

  // Adopt the account's saved theme once, if this device hasn't picked one itself.
  const accountTheme = me.data?.profile?.theme_preference;
  const { hasStoredChoice, update } = prefs;
  useEffect(() => {
    if (accountTheme && !hasStoredChoice) update("theme", accountTheme);
  }, [accountTheme, hasStoredChoice, update]);

  const login = useCallback(
    async (identifier: string, password: string): Promise<LoginResult> => {
      const result = await api.login(identifier, password);
      if ("access" in result) {
        queryClient.setQueryData(["me"], result.user);
        setLoggedIn(true);
        return { twoFactorRequired: false };
      }
      return { twoFactorRequired: true, challenge: result.challenge };
    },
    [queryClient],
  );
  const loginWithGoogle = useCallback(
    async (idToken: string): Promise<LoginResult> => {
      const result = await api.googleLogin(idToken);
      if ("access" in result) {
        queryClient.setQueryData(["me"], result.user);
        setLoggedIn(true);
        return { twoFactorRequired: false };
      }
      return { twoFactorRequired: true, challenge: result.challenge };
    },
    [queryClient],
  );
  const verifyTwoFactor = useCallback(
    async (challenge: string, code: string) => {
      const user = await api.verifyTwoFactor(challenge, code);
      queryClient.setQueryData(["me"], user);
      setLoggedIn(true);
    },
    [queryClient],
  );
  const register = useCallback(
    async (payload: Record<string, string>) => {
      const user = await api.register(payload);
      queryClient.setQueryData(["me"], user);
      setLoggedIn(true);
    },
    [queryClient],
  );
  const logout = useCallback(async () => {
    await api.logout();
    setLoggedIn(false);
    queryClient.clear();
  }, [queryClient]);

  const value = useMemo<AuthContext>(
    () => ({ user: loggedIn ? (me.data ?? null) : null, loggedIn, loading: loggedIn && me.isPending, login, loginWithGoogle, verifyTwoFactor, register, logout }),
    [loggedIn, me.data, me.isPending, login, loginWithGoogle, verifyTwoFactor, register, logout],
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAuth() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
