import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api } from "../api.js";

const AuthCtx = createContext(null);
export const useAuth = () => useContext(AuthCtx);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [googleClientId, setGoogleClientId] = useState(null);

  const refresh = useCallback(async () => {
    try {
      setUser(await api.me());
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    api.authConfig().then((c) => setGoogleClientId(c.google_client_id)).catch(() => {});
  }, [refresh]);

  // Session expired mid-use: sign out locally; the route guard sends the user to sign-in with
  // ?next=<this page>, and they come straight back to the same ticket afterwards.
  const [expired, setExpired] = useState(false);
  useEffect(() => {
    const onExpired = () => setUser((u) => { if (u) setExpired(true); return null; });
    window.addEventListener("session-expired", onExpired);
    return () => window.removeEventListener("session-expired", onExpired);
  }, []);

  const value = {
    user,
    loading,
    expired,
    googleClientId,
    refresh,
    login: async (email, password, remember) => { setUser(await api.login(email, password, remember)); setExpired(false); },
    signup: async (payload) => setUser(await api.signup(payload)),
    google: async (credential) => {
      const u = await api.google(credential);
      setUser(u);
      return u;
    },
    updateMe: async (payload) => setUser(await api.updateMe(payload)),
    logout: async () => {
      try {
        await api.logout();
      } finally {
        setUser(null);
      }
    },
  };
  return <AuthCtx.Provider value={value}>{children}</AuthCtx.Provider>;
}
