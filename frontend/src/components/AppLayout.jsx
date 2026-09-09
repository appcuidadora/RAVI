import { useEffect, useState } from "react";
import { NavLink, Outlet, useNavigate, Link } from "react-router-dom";
import {
  LayoutDashboard, MessageSquare, FileText, Users, BellRing,
  PhoneCall, ShieldCheck, SlidersHorizontal, LogOut, Menu,
} from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { api } from "@/lib/api";
import RaviLogo from "@/components/RaviLogo";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Button } from "@/components/ui/button";

const NAV = [
  { module: "dashboard", label: "Visão Geral", icon: LayoutDashboard, path: "/dashboard", tid: "sidebar-link-dashboard" },
  { module: "conversas", label: "Conversas", icon: MessageSquare, path: "/conversas", tid: "sidebar-link-conversas" },
  { module: "processos", label: "Processos", icon: FileText, path: "/processos", tid: "sidebar-link-processos" },
  { module: "clientes", label: "Clientes", icon: Users, path: "/clientes", tid: "sidebar-link-clientes" },
  { module: "alertas", label: "Alertas", icon: BellRing, path: "/alertas", tid: "sidebar-link-alertas" },
  { module: "whatsapp", label: "WhatsApp", icon: PhoneCall, path: "/whatsapp", tid: "sidebar-link-whatsapp" },
  { module: "equipe", label: "Equipe", icon: ShieldCheck, path: "/equipe", tid: "sidebar-link-equipe" },
  { module: "configuracoes", label: "Configurações", icon: SlidersHorizontal, path: "/configuracoes", tid: "sidebar-link-configuracoes" },
];

function NavItems({ onNavigate, permissions }) {
  return (
    <nav className="flex flex-col gap-1 px-3">
      {NAV.filter((n) => permissions?.[n.module]).map((n) => (
        <NavLink
          key={n.path}
          to={n.path}
          onClick={onNavigate}
          data-testid={n.tid}
          className={({ isActive }) =>
            `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors duration-200 ${
              isActive
                ? "bg-[#1E2235] text-zinc-100 border border-[#3F476C]"
                : "text-zinc-400 hover:text-zinc-100 hover:bg-[#161925] border border-transparent"
            }`
          }
        >
          <n.icon size={17} strokeWidth={1.8} />
          {n.label}
        </NavLink>
      ))}
    </nav>
  );
}

export default function AppLayout() {
  const { user, office, logout } = useAuth();
  const navigate = useNavigate();
  const [waStatus, setWaStatus] = useState(null);
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    api.get("/whatsapp/status").then((r) => setWaStatus(r.data)).catch(() => {});
  }, []);

  const handleLogout = async () => {
    await logout();
    navigate("/login");
  };

  const connected = waStatus?.connection?.status === "connected";
  const sidebar = (
    <div className="flex flex-col h-full">
      <div className="h-14 flex items-center px-5 border-b border-[#23283E]">
        <RaviLogo size={30} />
      </div>
      <div className="flex-1 py-4 overflow-y-auto">
        <NavItems permissions={user?.permissions} onNavigate={() => setMobileOpen(false)} />
      </div>
      <div className="p-4 border-t border-[#23283E] space-y-2">
        <p className="text-xs text-zinc-500 truncate">{office?.name || "Meu escritório"}</p>
        <p className="text-[10px] font-mono-code uppercase tracking-widest text-zinc-600">RAVI Atendimento</p>
        <button onClick={handleLogout} data-testid="sidebar-logout-btn"
          className="flex items-center gap-2 text-xs text-zinc-500 hover:text-rose-400 transition-colors duration-150 mt-1">
          <LogOut size={13} /> Sair da conta
        </button>
      </div>
    </div>
  );

  return (
    <div className="flex h-screen bg-[#090A0F]" data-testid="app-shell">
      <aside className="hidden lg:flex w-64 shrink-0 border-r border-[#23283E] bg-[#0B0D14] flex-col">
        {sidebar}
      </aside>

      <div className="flex-1 flex flex-col min-w-0">
        <header className="h-14 border-b border-[#23283E] bg-[#0B0D14]/80 backdrop-blur-md px-4 lg:px-6 flex items-center justify-between sticky top-0 z-40">
          <div className="flex items-center gap-3">
            <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
              <SheetTrigger asChild>
                <Button variant="ghost" size="icon" className="lg:hidden" data-testid="mobile-menu-btn">
                  <Menu size={18} />
                </Button>
              </SheetTrigger>
              <SheetContent side="left" className="w-64 p-0 bg-[#0B0D14] border-[#23283E]">
                {sidebar}
              </SheetContent>
            </Sheet>
            <span className="font-mono-code text-[10px] uppercase tracking-widest text-zinc-500 hidden sm:block">
              {office?.name}
            </span>
          </div>

          <div className="flex items-center gap-3">
            <Link to="/whatsapp" data-testid="topbar-whatsapp-status">
              <div className="flex items-center gap-2 rounded-full border border-[#23283E] bg-[#0F111A] px-3 py-1.5 hover:border-indigo-500/40 transition-colors duration-200">
                <span className={`w-2 h-2 rounded-full pulse-dot ${connected ? "bg-emerald-500" : "bg-zinc-600"}`} />
                <span className="text-xs text-zinc-400 hidden sm:block">
                  {connected ? `WhatsApp ativo ${waStatus.connection.display_phone_number || ""}` : "WhatsApp não conectado"}
                </span>
              </div>
            </Link>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button data-testid="user-menu-btn" className="flex items-center gap-2 rounded-full border border-[#23283E] bg-[#0F111A] pl-1 pr-3 py-1 hover:border-indigo-500/40 transition-colors duration-200">
                  <span className="w-7 h-7 rounded-full brand-gradient flex items-center justify-center text-xs font-bold text-white">
                    {(user?.name || "U")[0].toUpperCase()}
                  </span>
                  <span className="text-xs text-zinc-300 hidden sm:block">Dr(a). {user?.name}</span>
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="bg-[#0F111A] border-[#23283E]">
                <DropdownMenuItem onClick={handleLogout} data-testid="logout-btn" className="text-rose-400 focus:text-rose-300 cursor-pointer">
                  <LogOut size={14} className="mr-2" /> Sair
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </header>

        <main className="flex-1 overflow-y-auto bg-[#090A0F] grid-bg">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
