import { useEffect, useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import RaviLogo from "@/components/RaviLogo";
import {
  LayoutDashboard, Building2, Layers, Banknote, PhoneCall,
  LifeBuoy, BarChart3, ScrollText, SlidersHorizontal, LogOut, Menu,
} from "lucide-react";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";

const NAV = [
  { label: "Dashboard", icon: LayoutDashboard, path: "/admin", end: true, tid: "admin-nav-dashboard" },
  { label: "Escritórios", icon: Building2, path: "/admin/escritorios", tid: "admin-nav-escritorios" },
  { label: "Planos", icon: Layers, path: "/admin/planos", tid: "admin-nav-planos" },
  { label: "Financeiro", icon: Banknote, path: "/admin/financeiro", tid: "admin-nav-financeiro" },
  { label: "WhatsApp / Meta", icon: PhoneCall, path: "/admin/whatsapp", tid: "admin-nav-whatsapp" },
  { label: "Suporte", icon: LifeBuoy, path: "/admin/suporte", tid: "admin-nav-suporte" },
  { label: "Relatórios", icon: BarChart3, path: "/admin/relatorios", tid: "admin-nav-relatorios" },
  { label: "Logs", icon: ScrollText, path: "/admin/logs", tid: "admin-nav-logs" },
  { label: "Configurações", icon: SlidersHorizontal, path: "/admin/configuracoes", tid: "admin-nav-configuracoes" },
];

export default function AdminLayout() {
  const navigate = useNavigate();
  const [admin, setAdmin] = useState(null);
  const [loading, setLoading] = useState(true);
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    api.get("/admin/auth/me")
      .then((r) => setAdmin(r.data.admin))
      .catch(() => navigate("/admin/login", { replace: true }))
      .finally(() => setLoading(false));
  }, [navigate]);

  const logout = async () => {
    try { await api.post("/admin/auth/logout"); } catch {}
    navigate("/admin/login");
  };

  if (loading) {
    return <div className="min-h-screen bg-[#090A0F] flex items-center justify-center text-zinc-500 text-sm" data-testid="admin-loading">Carregando RAVI ADMIN…</div>;
  }

  const sidebar = (
    <div className="flex flex-col h-full">
      <div className="h-14 flex items-center gap-2.5 px-5 border-b border-[#23283E]">
        <RaviLogo size={26} withName={false} />
        <span className="font-display font-bold text-zinc-100">RAVI <span className="brand-gradient-text">ADMIN</span></span>
      </div>
      <nav className="flex-1 py-4 px-3 flex flex-col gap-1 overflow-y-auto">
        {NAV.map((n) => (
          <NavLink key={n.path} to={n.path} end={n.end} onClick={() => setMobileOpen(false)} data-testid={n.tid}
            className={({ isActive }) =>
              `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors duration-200 ${
                isActive ? "bg-[#1E2235] text-zinc-100 border border-[#3F476C]"
                         : "text-zinc-400 hover:text-zinc-100 hover:bg-[#161925] border border-transparent"}`}>
            <n.icon size={17} strokeWidth={1.8} /> {n.label}
          </NavLink>
        ))}
      </nav>
      <div className="p-4 border-t border-[#23283E]">
        <p className="text-xs text-zinc-500 truncate">{admin?.name}</p>
        <p className="text-[10px] font-mono-code uppercase tracking-widest text-zinc-600">{admin?.role}</p>
        <button onClick={logout} data-testid="admin-logout-btn"
          className="flex items-center gap-2 text-xs text-zinc-500 hover:text-rose-400 transition-colors duration-150 mt-2">
          <LogOut size={13} /> Sair
        </button>
      </div>
    </div>
  );

  return (
    <div className="flex h-screen bg-[#090A0F]" data-testid="admin-shell">
      <aside className="hidden lg:flex w-64 shrink-0 border-r border-[#23283E] bg-[#0B0D14] flex-col">{sidebar}</aside>
      <div className="flex-1 flex flex-col min-w-0">
        <header className="h-14 border-b border-[#23283E] bg-[#0B0D14]/80 backdrop-blur-md px-4 lg:px-6 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
              <SheetTrigger asChild>
                <Button variant="ghost" size="icon" className="lg:hidden" data-testid="admin-mobile-menu-btn"><Menu size={18} /></Button>
              </SheetTrigger>
              <SheetContent side="left" className="w-64 p-0 bg-[#0B0D14] border-[#23283E]">{sidebar}</SheetContent>
            </Sheet>
            <span className="font-mono-code text-[10px] uppercase tracking-widest text-zinc-500">Plataforma RAVI</span>
          </div>
          <span className="text-xs text-zinc-500">{admin?.email}</span>
        </header>
        <main className="flex-1 overflow-y-auto bg-[#090A0F] grid-bg"><Outlet /></main>
      </div>
    </div>
  );
}
