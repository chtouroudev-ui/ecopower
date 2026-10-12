import React, { useCallback, useEffect, useState } from 'react';
import { WarrantyCertificateModal, printCertificateDirectly } from '../components/WarrantyCertificateModal';
import { useAuth } from '../context/AuthContext';
import {
  LayoutDashboard, ShoppingBag, Package, Building2, Award, RefreshCw, LogOut,
  ArrowLeft, Lock, AlertCircle, Droplets, Menu, X,
} from 'lucide-react';
import { Toast } from './admin/ui';
import { Overview } from './admin/Overview';
import { Orders } from './admin/Orders';
import { Products } from './admin/Products';
import { Leads } from './admin/Leads';
import { Certificates } from './admin/Certificates';

function LoginScreen({ onExit }) {
  const { login, logout } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const submit = async (e) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const u = await login(email, password);
      if (u.role !== 'admin') {
        logout();
        throw new Error("Ce compte n'a pas accès à l'administration.");
      }
    } catch (err) {
      setError(err instanceof TypeError ? 'Serveur injoignable. Vérifiez que le serveur est démarré.' : err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-100 flex items-center justify-center p-4">
      <div className="w-full max-w-sm">
        <div className="flex items-center justify-center gap-2 mb-6">
          <div className="w-10 h-10 rounded-xl bg-blue-600 flex items-center justify-center text-white">
            <Droplets className="w-5 h-5" />
          </div>
          <span className="font-black text-xl text-slate-900">ECO<span className="text-blue-600">POWER</span> Admin</span>
        </div>
        <form onSubmit={submit} className="bg-white rounded-2xl p-6 sm:p-8 shadow-xl border border-slate-200 space-y-4">
          <div className="flex items-center gap-2 text-slate-900 font-bold">
            <Lock className="w-4 h-4 text-blue-600" /> Connexion administrateur
          </div>
          {error && (
            <div role="alert" className="p-3 bg-red-50 border border-red-200 rounded-xl text-xs text-red-700 font-semibold flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0" /> {error}
            </div>
          )}
          <div>
            <label className="text-xs font-bold text-slate-600 block mb-1">Email</label>
            <input
              type="email" required autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)}
              className="w-full px-3.5 py-2.5 border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="text-xs font-bold text-slate-600 block mb-1">Mot de passe</label>
            <input
              type="password" required autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)}
              className="w-full px-3.5 py-2.5 border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <button type="submit" disabled={loading} className="w-full py-2.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-60 text-white font-bold rounded-xl transition">
            {loading ? 'Connexion…' : 'Se connecter'}
          </button>
        </form>
        {onExit && (
          <button onClick={onExit} className="mt-4 w-full text-xs text-slate-500 hover:text-slate-800 flex items-center justify-center gap-1.5">
            <ArrowLeft className="w-3.5 h-3.5" /> Retour au site
          </button>
        )}
      </div>
    </div>
  );
}

const TABS = [
  { id: 'dashboard', label: 'Tableau de bord', icon: LayoutDashboard },
  { id: 'orders', label: 'Commandes', icon: ShoppingBag },
  { id: 'products', label: 'Produits & stock', icon: Package },
  { id: 'leads', label: 'Demandes pro', icon: Building2 },
  { id: 'certs', label: 'Garanties', icon: Award },
];

const DEFAULT_FILTER = { orders: 'open', products: 'all', leads: 'all' };

export const AdminDashboard = ({ onExit }) => {
  const { user, isAdmin, token, logout } = useAuth();

  const [tab, setTab] = useState('dashboard');
  const [filters, setFilters] = useState(DEFAULT_FILTER);
  const [openOrderId, setOpenOrderId] = useState(null);
  const [navOpen, setNavOpen] = useState(false);

  const [orders, setOrders] = useState([]);
  const [products, setProducts] = useState([]);
  const [leads, setLeads] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [lastSync, setLastSync] = useState(null);
  const [toast, setToast] = useState(null);
  const [certificateId, setCertificateId] = useState(null);

  const notify = useCallback((message, type = 'success') => setToast({ message, type, at: Date.now() }), []);
  const closeToast = useCallback(() => setToast(null), []);

  const api = useCallback(
    async (method, url, body) => {
      const res = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: body ? JSON.stringify(body) : undefined,
      });
      if (res.status === 401 || res.status === 403) {
        logout();
        throw new Error('Session expirée, reconnectez-vous.');
      }
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.error || 'Opération impossible.');
      return data;
    },
    [token, logout]
  );

  const fetchData = useCallback(
    async ({ silent = false } = {}) => {
      if (!token) return;
      if (!silent) setLoading(true);
      try {
        const [o, p, l, s] = await Promise.all([
          api('GET', '/api/orders'),
          api('GET', '/api/products'),
          api('GET', '/api/leads'),
          api('GET', '/api/stats'),
        ]);
        setOrders(Array.isArray(o) ? o : []);
        setProducts(Array.isArray(p) ? p : []);
        setLeads(Array.isArray(l) ? l : []);
        setStats(s && !s.error ? s : null);
        setLastSync(new Date());
      } catch (err) {
        notify(err instanceof TypeError ? 'Serveur injoignable.' : err.message, 'error');
      } finally {
        setLoading(false);
      }
    },
    [token, api, notify]
  );

  useEffect(() => {
    if (isAdmin && token) fetchData();
  }, [isAdmin, token, fetchData]);

  // Actualisation automatique toutes les 60 s pour voir arriver les nouvelles commandes
  useEffect(() => {
    if (!isAdmin) return undefined;
    const id = setInterval(() => fetchData({ silent: true }), 60000);
    return () => clearInterval(id);
  }, [isAdmin, fetchData]);

  const guard = (fn, success) => async (...args) => {
    try {
      await fn(...args);
      if (success) notify(typeof success === 'function' ? success(...args) : success);
      return true;
    } catch (err) {
      notify(err.message, 'error');
      return false;
    }
  };

  const STATUS_MSG = {
    confirmed: 'Commande confirmée',
    shipped: 'Commande expédiée',
    delivered: 'Commande livrée et encaissée',
    cancelled: 'Commande annulée, stock remis à jour',
    pending: 'Commande réactivée',
  };

  const updateOrderStatus = guard(async (id, status) => {
    await api('PUT', `/api/orders/${id}`, { status });
    setOrders((prev) => prev.map((o) => (o.id === id ? { ...o, status } : o)));
    fetchData({ silent: true });
  }, (_id, status) => STATUS_MSG[status]);

  const updateOrderNotes = guard(async (id, notes) => {
    await api('PUT', `/api/orders/${id}`, { notes });
    setOrders((prev) => prev.map((o) => (o.id === id ? { ...o, notes } : o)));
  }, 'Note enregistrée');

  const createProduct = guard(async (data) => {
    const created = await api('POST', '/api/products', data);
    setProducts((prev) => [...prev, { ...data, ...created }]);
  }, 'Produit ajouté');

  const updateProduct = guard(async (id, data) => {
    await api('PUT', `/api/products/${id}`, data);
    setProducts((prev) => prev.map((p) => (p.id === id ? { ...p, ...data } : p)));
  }, 'Produit mis à jour');

  const deleteProduct = guard(async (id) => {
    await api('DELETE', `/api/products/${id}`);
    setProducts((prev) => prev.filter((p) => p.id !== id));
  }, 'Produit supprimé');

  const updateLead = guard(async (id, data) => {
    await api('PUT', `/api/leads/${id}`, data);
    setLeads((prev) => prev.map((l) => (l.id === id ? { ...l, ...data } : l)));
  }, 'Demande mise à jour');

  const printCertificate = async (orderId) => {
    try {
      const res = await fetch(`/api/certificate/${orderId}`);
      if (!res.ok) throw new Error();
      printCertificateDirectly(await res.json());
    } catch {
      setCertificateId(orderId);
    }
  };

  const goTo = (target, filter) => {
    setTab(target);
    if (filter) setFilters((f) => ({ ...f, [target]: filter }));
    setNavOpen(false);
  };

  if (!isAdmin) return <LoginScreen onExit={onExit} />;

  const pendingCount = orders.filter((o) => o.status === 'pending').length;
  const newLeads = leads.filter((l) => l.status === 'new').length;
  const badges = { orders: pendingCount, leads: newLeads };
  const current = TABS.find((t) => t.id === tab);

  const nav = (
    <nav className="flex-1 p-3 space-y-0.5">
      {TABS.map((t) => {
        const Icon = t.icon;
        const active = tab === t.id;
        return (
          <button
            key={t.id}
            onClick={() => goTo(t.id)}
            className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-semibold transition ${
              active ? 'bg-white/10 text-white' : 'text-slate-400 hover:text-white hover:bg-white/5'
            }`}
          >
            <Icon className="w-4 h-4" />
            {t.label}
            {badges[t.id] > 0 && (
              <span className="ml-auto min-w-[20px] text-center bg-amber-400 text-slate-900 text-[10px] font-black px-1.5 py-0.5 rounded-full">
                {badges[t.id]}
              </span>
            )}
          </button>
        );
      })}
    </nav>
  );

  const sidebarFooter = (
    <div className="p-3 border-t border-white/10 space-y-1">
      <div className="px-3 py-2">
        <div className="text-xs font-bold text-white truncate">{user?.name}</div>
        <div className="text-[11px] text-slate-500 truncate">{user?.email}</div>
      </div>
      {onExit && (
        <button onClick={onExit} className="w-full flex items-center gap-2 px-3 py-2 text-xs text-slate-400 hover:text-white rounded-lg hover:bg-white/5">
          <ArrowLeft className="w-3.5 h-3.5" /> Voir le site
        </button>
      )}
      <button onClick={logout} className="w-full flex items-center gap-2 px-3 py-2 text-xs text-slate-400 hover:text-red-300 rounded-lg hover:bg-white/5">
        <LogOut className="w-3.5 h-3.5" /> Déconnexion
      </button>
    </div>
  );

  const brand = (
    <div className="px-5 py-5 flex items-center gap-2.5">
      <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center text-white">
        <Droplets className="w-4 h-4" />
      </div>
      <div>
        <div className="text-sm font-black text-white tracking-tight">ECOPOWER</div>
        <div className="text-[10px] text-slate-500 uppercase tracking-wider">Administration</div>
      </div>
    </div>
  );

  return (
    <div className="flex min-h-screen bg-slate-50 font-sans">
      <aside className="w-60 shrink-0 bg-slate-950 hidden lg:flex flex-col sticky top-0 h-screen">
        {brand}
        {nav}
        {sidebarFooter}
      </aside>

      {navOpen && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div className="absolute inset-0 bg-slate-900/50" onClick={() => setNavOpen(false)} />
          <aside className="absolute inset-y-0 left-0 w-64 bg-slate-950 flex flex-col animate-in slide-in-from-left duration-200">
            <div className="flex items-center justify-between pr-3">
              {brand}
              <button onClick={() => setNavOpen(false)} className="p-2 text-slate-400" aria-label="Fermer le menu">
                <X className="w-5 h-5" />
              </button>
            </div>
            {nav}
            {sidebarFooter}
          </aside>
        </div>
      )}

      <main className="flex-1 min-w-0 flex flex-col">
        <header className="bg-white/90 backdrop-blur border-b border-slate-200 px-4 sm:px-6 py-3 flex items-center justify-between sticky top-0 z-30">
          <div className="flex items-center gap-3">
            <button onClick={() => setNavOpen(true)} className="lg:hidden p-2 -ml-2 rounded-lg hover:bg-slate-100" aria-label="Menu">
              <Menu className="w-5 h-5" />
            </button>
            <div>
              <h1 className="text-base sm:text-lg font-black text-slate-900">{current?.label}</h1>
              {lastSync && <p className="text-[11px] text-slate-400">Mis à jour à {lastSync.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })}</p>}
            </div>
          </div>
          <button
            onClick={() => fetchData()}
            className="flex items-center gap-1.5 px-3 py-2 text-xs font-bold text-slate-600 hover:text-blue-700 border border-slate-200 rounded-xl hover:bg-blue-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            <span className="hidden sm:inline">Actualiser</span>
          </button>
        </header>

        <div className="flex-1 p-4 sm:p-6 max-w-[1400px] w-full mx-auto">
          {loading && !lastSync ? (
            <div className="space-y-4 animate-pulse">
              <div className="grid grid-cols-2 xl:grid-cols-4 gap-4">
                {[0, 1, 2, 3].map((i) => <div key={i} className="h-24 rounded-2xl bg-slate-200/70" />)}
              </div>
              <div className="h-64 rounded-2xl bg-slate-200/70" />
            </div>
          ) : (
            <>
              {tab === 'dashboard' && (
                <Overview
                  stats={stats}
                  orders={orders}
                  leads={leads}
                  products={products}
                  goTo={goTo}
                  openOrder={(id) => {
                    goTo('orders');
                    setOpenOrderId(id);
                  }}
                />
              )}
              {tab === 'orders' && (
                <Orders
                  orders={orders}
                  filter={filters.orders}
                  setFilter={(v) => setFilters((f) => ({ ...f, orders: v }))}
                  openId={openOrderId}
                  setOpenId={setOpenOrderId}
                  onStatus={updateOrderStatus}
                  onNotes={updateOrderNotes}
                  onCertificate={setCertificateId}
                  onPrint={printCertificate}
                />
              )}
              {tab === 'products' && (
                <Products
                  products={products}
                  filter={filters.products}
                  setFilter={(v) => setFilters((f) => ({ ...f, products: v }))}
                  onCreate={createProduct}
                  onUpdate={updateProduct}
                  onDelete={deleteProduct}
                />
              )}
              {tab === 'leads' && (
                <Leads
                  leads={leads}
                  filter={filters.leads}
                  setFilter={(v) => setFilters((f) => ({ ...f, leads: v }))}
                  onUpdate={updateLead}
                />
              )}
              {tab === 'certs' && <Certificates orders={orders} onView={setCertificateId} onPrint={printCertificate} />}
            </>
          )}
        </div>
      </main>

      {certificateId && <WarrantyCertificateModal orderId={certificateId} onClose={() => setCertificateId(null)} />}
      <Toast toast={toast} onClose={closeToast} />
    </div>
  );
};
