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

  const value = {
    user,
    loading,
    googleClientId,
    refresh,
    login: async (email, password) => setUser(await api.login(email, password)),
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
