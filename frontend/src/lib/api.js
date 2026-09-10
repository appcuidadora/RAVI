import axios from "axios";

export const api = axios.create({
  baseURL: `${process.env.REACT_APP_BACKEND_URL}/api`,
  withCredentials: true,
});

api.interceptors.request.use((config) => {
  try {
    const imp = sessionStorage.getItem("ravi_impersonate");
    if (imp) config.headers.Authorization = `Bearer ${JSON.parse(imp).token}`;
  } catch {}
  return config;
});

api.interceptors.response.use(
  (r) => r,
  async (err) => {
    const orig = err.config || {};
    if (err.response?.status === 401 && !orig._retried && !(orig.url || "").includes("/auth/")) {
      orig._retried = true;
      try {
        await api.post("/auth/refresh");
        return api(orig);
      } catch {
        return Promise.reject(err);
      }
    }
    return Promise.reject(err);
  }
);

export function apiError(e, fallback = "Algo deu errado. Tente novamente.") {
  const detail = e?.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map((d) => d?.msg || "").filter(Boolean).join(" ");
  return fallback;
}
