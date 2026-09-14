import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate, useLocation } from "react-router-dom";
import { AuthProvider, useAuth } from "@/context/AuthContext";
import { Toaster } from "@/components/ui/sonner";
import AppLayout from "@/components/AppLayout";
import RaviLogo from "@/components/RaviLogo";
import Login from "@/pages/Login";
import Register from "@/pages/Register";
import ForgotPassword from "@/pages/ForgotPassword";
import ResetPassword from "@/pages/ResetPassword";
import Onboarding from "@/pages/Onboarding";
import Dashboard from "@/pages/Dashboard";
import Conversas from "@/pages/Conversas";
import Processos from "@/pages/Processos";
import ProcessoDetalhe from "@/pages/ProcessoDetalhe";
import Clientes from "@/pages/Clientes";
import ClienteDetalhe from "@/pages/ClienteDetalhe";
import Alertas from "@/pages/Alertas";
import Equipe from "@/pages/Equipe";
import Configuracoes from "@/pages/Configuracoes";
import WhatsAppPage from "@/pages/WhatsAppPage";
import AdminLogin from "@/pages/admin/AdminLogin";
import AdminLayout from "@/pages/admin/AdminLayout";
import AdminDashboard from "@/pages/admin/AdminDashboard";
import AdminEscritorios from "@/pages/admin/AdminEscritorios";
import AdminPlanos from "@/pages/admin/AdminPlanos";
import AdminFinanceiro from "@/pages/admin/AdminFinanceiro";
import AdminWhatsApp from "@/pages/admin/AdminWhatsApp";
import AdminSuporte from "@/pages/admin/AdminSuporte";
import AdminRelatorios from "@/pages/admin/AdminRelatorios";
import AdminLogs from "@/pages/admin/AdminLogs";
import AdminConfiguracoes from "@/pages/admin/AdminConfiguracoes";

function FullScreenLoader() {
  return (
    <div className="min-h-screen bg-[#090A0F] grid-bg flex flex-col items-center justify-center gap-4" data-testid="auth-loading">
      <RaviLogo size={44} withName={false} />
      <p className="text-xs font-mono-code uppercase tracking-widest text-zinc-500">Carregando RAVI…</p>
    </div>
  );
}

function RequireAuth({ children }) {
  const { status, user } = useAuth();
  const location = useLocation();
  if (status === "loading") return <FullScreenLoader />;
  if (status === "guest") return <Navigate to="/login" state={{ from: location.pathname }} replace />;
  const needsOnboarding = !user?.onboarding_completed;
  if (needsOnboarding && location.pathname !== "/onboarding") return <Navigate to="/onboarding" replace />;
  if (!needsOnboarding && location.pathname === "/onboarding") return <Navigate to="/dashboard" replace />;
  return children;
}

function RequirePerm({ module, children }) {
  const { user } = useAuth();
  if (user && !user.permissions?.[module]) return <Navigate to="/dashboard" replace />;
  return children;
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/cadastro" element={<Register />} />
      <Route path="/esqueci-senha" element={<ForgotPassword />} />
      <Route path="/reset-password" element={<ResetPassword />} />
      <Route path="/onboarding" element={<RequireAuth><Onboarding /></RequireAuth>} />
      <Route element={<RequireAuth><AppLayout /></RequireAuth>}>
        <Route path="/dashboard" element={<RequirePerm module="dashboard"><Dashboard /></RequirePerm>} />
        <Route path="/conversas" element={<RequirePerm module="conversas"><Conversas /></RequirePerm>} />
        <Route path="/processos" element={<RequirePerm module="processos"><Processos /></RequirePerm>} />
        <Route path="/processos/:id" element={<RequirePerm module="processos"><ProcessoDetalhe /></RequirePerm>} />
        <Route path="/clientes" element={<RequirePerm module="clientes"><Clientes /></RequirePerm>} />
        <Route path="/clientes/:id" element={<RequirePerm module="clientes"><ClienteDetalhe /></RequirePerm>} />
        <Route path="/alertas" element={<RequirePerm module="alertas"><Alertas /></RequirePerm>} />
        <Route path="/equipe" element={<RequirePerm module="equipe"><Equipe /></RequirePerm>} />
        <Route path="/configuracoes" element={<RequirePerm module="configuracoes"><Configuracoes /></RequirePerm>} />
        <Route path="/whatsapp" element={<RequirePerm module="whatsapp"><WhatsAppPage /></RequirePerm>} />
      </Route>
      <Route path="/admin/login" element={<AdminLogin />} />
      <Route path="/admin" element={<AdminLayout />}>
        <Route index element={<AdminDashboard />} />
        <Route path="escritorios" element={<AdminEscritorios />} />
        <Route path="planos" element={<AdminPlanos />} />
        <Route path="financeiro" element={<AdminFinanceiro />} />
        <Route path="whatsapp" element={<AdminWhatsApp />} />
        <Route path="suporte" element={<AdminSuporte />} />
        <Route path="relatorios" element={<AdminRelatorios />} />
        <Route path="logs" element={<AdminLogs />} />
        <Route path="configuracoes" element={<AdminConfiguracoes />} />
      </Route>
      <Route path="/" element={<Navigate to="/dashboard" replace />} />
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}

function App() {
  return (
    <div className="App">
      <BrowserRouter>
        <AuthProvider>
          <AppRoutes />
          <Toaster theme="dark" position="top-right" richColors />
        </AuthProvider>
      </BrowserRouter>
    </div>
  );
}

export default App;
