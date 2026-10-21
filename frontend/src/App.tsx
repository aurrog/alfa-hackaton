import { Navigate, Route, Routes, useLocation } from 'react-router-dom';
import { useAuth } from './auth/AuthContext';
import { Loading } from './components/ui';
import { BankLayout } from './layouts/BankLayout';
import { ClientLayout } from './layouts/ClientLayout';
import { LoginPage } from './pages/LoginPage';
import { DashboardPage } from './pages/bank/DashboardPage';
import { DossierPage } from './pages/bank/DossierPage';
import { AuditPage, PolicyPage, SystemPage } from './pages/bank/PolicyPages';
import { QueuePage } from './pages/bank/QueuePage';
import { ApplicationEditPage } from './pages/client/ApplicationEditPage';
import { ApplicationPage } from './pages/client/ApplicationPage';
import { HomePage } from './pages/client/HomePage';
import { ApplicationsPage, ConnectCompanyPage, LoansPage, NotFoundPage } from './pages/client/OtherPages';
import { ProductsPage } from './pages/client/ProductsPage';

function Guard({ kind, children }: { kind: 'client' | 'bank'; children: JSX.Element }) {
  const { user, ready } = useAuth();
  const loc = useLocation();
  if (!ready) return <Loading />;
  if (!user) return <Navigate to="/login" replace state={{ from: loc.pathname }} />;
  if (user.kind !== kind) return <Navigate to={user.kind === 'bank' ? '/bank' : '/'} replace />;
  return children;
}

export function App() {
  const { user, ready } = useAuth();
  return (
    <Routes>
      <Route path="/login" element={ready && user ? <Navigate to={user.kind === 'bank' ? '/bank' : '/'} replace /> : <LoginPage />} />
      <Route
        path="/bank"
        element={
          <Guard kind="bank">
            <BankLayout />
          </Guard>
        }
      >
        <Route index element={<QueuePage />} />
        <Route path="applications/:id" element={<DossierPage />} />
        <Route path="dashboard" element={<DashboardPage />} />
        <Route path="policy" element={<PolicyPage />} />
        <Route path="audit" element={<AuditPage />} />
        <Route path="system" element={<SystemPage />} />
      </Route>
      <Route
        path="/"
        element={
          <Guard kind="client">
            <ClientLayout />
          </Guard>
        }
      >
        <Route index element={<HomePage />} />
        <Route path="products" element={<ProductsPage />} />
        <Route path="applications" element={<ApplicationsPage />} />
        <Route path="applications/:id" element={<ApplicationPage />} />
        <Route path="applications/:id/edit" element={<ApplicationEditPage />} />
        <Route path="loans" element={<LoansPage />} />
        <Route path="companies/connect" element={<ConnectCompanyPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}
