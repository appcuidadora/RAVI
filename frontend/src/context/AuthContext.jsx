import { createContext, useContext, useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [state, setState] = useState({ status: "loading", user: null, office: null });

  const load = useCallback(async () => {
    try {
      const { data } = await api.get("/auth/me");
      setState({ status: "authed", user: data.user, office: data.office });
    } catch {
      setState({ status: "guest", user: null, office: null });
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const login = async (email, password) => {
    const { data } = await api.post("/auth/login", { email, password });
    setState({ status: "authed", user: data.user, office: data.office });
    return data;
  };

  const logout = async () => {
    try { await api.post("/auth/logout"); } catch {}
    setState({ status: "guest", user: null, office: null });
  };

  return (
    <AuthContext.Provider value={{ ...state, login, logout, reload: load }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
