import React, { useState, useEffect } from 'react';
import { WarrantyCertificateModal } from '../components/WarrantyCertificateModal';
import { useAuth } from '../context/AuthContext';
import { 
  LayoutDashboard, 
  Package, 
  ShoppingBag, 
  Award, 
  Building2, 
  CheckCircle, 
  Clock, 
  Truck, 
  AlertTriangle, 
  Printer, 
  Edit3, 
  Save, 
  Plus, 
  Trash2,
  Search,
  RefreshCw,
  Eye,
  ShieldCheck,
  Lock,
  Database,
  ArrowRight,
  LogOut,
  UserCheck
} from 'lucide-react';

export const AdminDashboard = () => {
  const { user, isAdmin, token, login, logout } = useAuth();

  // Admin login local form state if not logged in
  const [adminEmail, setAdminEmail] = useState('admin@ecopower.tn');
  const [adminPassword, setAdminPassword] = useState('admin123');
  const [loginLoading, setLoginLoading] = useState(false);
  const [loginError, setLoginError] = useState(null);

  const [activeTab, setActiveTab] = useState('orders'); // orders | stock | certificates | leads
  const [orders, setOrders] = useState([]);
  const [products, setProducts] = useState([]);
  const [leads, setLeads] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedCertificate, setSelectedCertificate] = useState(null);
  const [editingProduct, setEditingProduct] = useState(null);
  const [editPrice, setEditPrice] = useState('');
  const [editStock, setEditStock] = useState('');
  const [searchSerial, setSearchSerial] = useState('');

  // Add Product Modal State
  const [showAddProductModal, setShowAddProductModal] = useState(false);
  const [newProd, setNewProd] = useState({
    name: '',
    nameAr: '',
    category: 'robinets',
    price: '',
    oldPrice: '',
    stock: '50',
    debit: '4 L/min',
    warranty: '3 ans',
    description: '',
    image: '/products/bague_mousseur_complet.jpg'
  });

  const fetchData = async () => {
    setLoading(true);
    try {
      const [ordRes, prodRes, leadRes] = await Promise.all([
        fetch('/api/orders').then(r => r.json()),
        fetch('/api/products').then(r => r.json()),
        fetch('/api/leads').then(r => r.json())
      ]);
      setOrders(Array.isArray(ordRes) ? ordRes : []);
      setProducts(Array.isArray(prodRes) ? prodRes : []);
      setLeads(Array.isArray(leadRes) ? leadRes : []);
    } catch (err) {
      console.error('Error fetching admin data:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isAdmin) {
      fetchData();
    }
  }, [isAdmin]);

  const handleAdminLogin = async (e) => {
    e.preventDefault();
    setLoginError(null);
    setLoginLoading(true);
    try {
      const loggedUser = await login(adminEmail, adminPassword);
      if (loggedUser.role !== 'admin') {
        throw new Error('Ce compte n\'a pas les privilèges administrateur.');
      }
    } catch (err) {
      setLoginError(err.message || 'Identifiants administrateur incorrects');
    } finally {
      setLoginLoading(false);
    }
  };

  const handleUpdateOrderStatus = async (orderId, newStatus) => {
    try {
      const res = await fetch(`/api/orders/${orderId}/status`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: newStatus })
      });
      if (res.ok) {
        setOrders(orders.map(o => o.id === orderId ? { ...o, status: newStatus } : o));
      }
    } catch (err) {
      console.error(err);
    }
  };

  const handleUpdateLeadStatus = async (leadId, newStatus) => {
    try {
      const res = await fetch(`/api/leads/${leadId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: newStatus })
      });
      if (res.ok) {
        setLeads(leads.map(l => l.id === leadId ? { ...l, status: newStatus } : l));
      }
    } catch (err) {
      console.error(err);
    }
  };

  const handleSaveProduct = async (productId) => {
    try {
      const res = await fetch(`/api/products/${productId}`, {
        method: 'PUT',
        headers: { 
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          price: parseFloat(editPrice),
          stock: parseInt(editStock, 10)
        })
      });
      if (res.ok) {
        const updated = await res.json();
        setProducts(products.map(p => p.id === productId ? { ...p, price: parseFloat(editPrice), stock: parseInt(editStock, 10) } : p));
        setEditingProduct(null);
      }
    } catch (err) {
      console.error(err);
    }
  };

  const handleDeleteProduct = async (productId) => {
    if (!window.confirm(`Êtes-vous sûr de vouloir supprimer ce produit (${productId}) ?`)) return;
    try {
      const res = await fetch(`/api/products/${productId}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        setProducts(products.filter(p => p.id !== productId));
      }
    } catch (err) {
      console.error(err);
    }
  };

  const handleCreateProduct = async (e) => {
    e.preventDefault();
    try {
      const prodId = 'prod-' + newProd.name.toLowerCase().replace(/[^a-z0-9]/g, '-').slice(0, 30);
      const res = await fetch('/api/products', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          id: prodId,
          name: newProd.name,
          nameAr: newProd.nameAr,
          category: newProd.category,
          price: parseFloat(newProd.price),
          oldPrice: newProd.oldPrice ? parseFloat(newProd.oldPrice) : null,
          stock: parseInt(newProd.stock, 10),
          debit: newProd.debit,
          warranty: newProd.warranty,
          description: newProd.description,
          image: newProd.image || '/products/bague_mousseur_complet.jpg',
          features: ['Technologie hydro-économe haute pression', 'Garantie officielle 3 ans', 'Matériau Delrin / Inox']
        })
      });

      if (res.ok) {
        const created = await res.json();
        setProducts([created, ...products]);
        setShowAddProductModal(false);
        setNewProd({
          name: '',
          nameAr: '',
          category: 'robinets',
          price: '',
          oldPrice: '',
          stock: '50',
          debit: '4 L/min',
          warranty: '3 ans',
          description: '',
          image: '/products/bague_mousseur_complet.jpg'
        });
      }
    } catch (err) {
      console.error(err);
    }
  };

  const handleViewCertificate = async (orderId) => {
    try {
      const res = await fetch(`/api/certificate/${orderId}`);
      if (res.ok) {
        const cert = await res.json();
        setSelectedCertificate(cert);
      }
    } catch (err) {
      console.error(err);
    }
  };

  // If NOT ADMIN -> show clean Admin Login screen
  if (!isAdmin) {
    return (
      <div className="min-h-[70vh] flex items-center justify-center p-4">
        <div className="w-full max-w-md bg-white rounded-3xl shadow-2xl border border-blue-100 overflow-hidden">
          <div className="bg-gradient-to-r from-blue-800 to-blue-950 p-8 text-white text-center relative">
            <div className="w-16 h-16 rounded-2xl bg-white/10 border border-white/20 mx-auto flex items-center justify-center mb-3">
              <Lock className="w-8 h-8 text-blue-200" />
            </div>
            <h2 className="text-2xl font-black font-serif">Administration EcoPower</h2>
            <p className="text-xs text-blue-200 mt-1">
              Connexion sécurisée au panneau de gestion MySQL
            </p>
            <div className="mt-3 inline-flex items-center space-x-1.5 px-3 py-1 bg-blue-900/60 rounded-full text-[11px] font-mono border border-blue-400/30">
              <Database className="w-3 h-3 text-blue-300" />
              <span>MySQL ecopower_db</span>
            </div>
          </div>

          <form onSubmit={handleAdminLogin} className="p-8 space-y-5">
            {loginError && (
              <div className="p-3 bg-red-50 border border-red-200 text-red-700 text-xs rounded-xl font-medium">
                {loginError}
              </div>
            )}

            <div>
              <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1">
                Identifiant Administrateur
              </label>
              <input
                type="email"
                required
                value={adminEmail}
                onChange={(e) => setAdminEmail(e.target.value)}
                className="w-full px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-blue-600 focus:bg-white text-slate-900"
              />
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1">
                Mot de Passe
              </label>
              <input
                type="password"
                required
                value={adminPassword}
                onChange={(e) => setAdminPassword(e.target.value)}
                className="w-full px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-blue-600 focus:bg-white text-slate-900"
              />
            </div>

            <button
              type="submit"
              disabled={loginLoading}
              className="w-full py-3 bg-blue-600 hover:bg-blue-700 text-white font-bold rounded-xl shadow-lg shadow-blue-500/25 flex items-center justify-center space-x-2 transition-all disabled:opacity-50"
            >
              {loginLoading ? (
                <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
              ) : (
                <>
                  <span>Accéder au Dashboard</span>
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>

            <div className="pt-4 border-t border-slate-100 text-center">
              <button
                type="button"
                onClick={() => {
                  setAdminEmail('admin@ecopower.tn');
                  setAdminPassword('admin123');
                }}
                className="text-xs text-blue-600 hover:text-blue-800 font-semibold"
              >
                ⚡ Remplir les identifiants Admin (admin@ecopower.tn / admin123)
              </button>
            </div>
          </form>
        </div>
      </div>
    );
  }

  // KPIs
  const totalRevenue = orders.reduce((sum, o) => sum + (o.total || 0), 0);
  const pendingOrders = orders.filter(o => o.status === 'pending').length;
  const lowStockCount = products.filter(p => (p.stock || 0) <= 20).length;

  const filteredOrdersForCertificates = orders.filter(ord => {
    if (!searchSerial) return true;
    const q = searchSerial.toLowerCase();
    const serialMatch = ord.certificateSerial?.toLowerCase().includes(q) ||
      ord.items?.some(it => it.serials?.some(s => s.toLowerCase().includes(q)));
    const clientMatch = ord.customer?.fullName?.toLowerCase().includes(q) || ord.id.toLowerCase().includes(q);
    return serialMatch || clientMatch;
  });

  return (
    <div className="py-8 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-8">
      
      {/* Header with MySQL status & Admin user badge */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center pb-6 border-b border-slate-200 gap-4">
        <div>
          <div className="flex flex-wrap items-center gap-2 mb-1.5">
            <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-blue-100 text-blue-800 text-xs font-bold uppercase tracking-wider">
              <LayoutDashboard className="w-3.5 h-3.5" />
              <span>Panneau de Contrôle Directeur</span>
            </div>
            <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-blue-50 border border-blue-200 text-blue-700 text-xs font-semibold">
              <Database className="w-3 h-3 text-blue-600" />
              <span>MySQL Connecté (ecopower_db)</span>
            </div>
          </div>
          <h1 className="text-3xl font-extrabold text-slate-900 font-serif">
            Interface d'Administration EcoPower
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Gestion des commandes, suivi des stocks, et émission des certificats de garantie officiels avec numéros de série.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <div className="hidden sm:flex items-center space-x-2 px-3 py-1.5 bg-slate-100 rounded-xl text-xs text-slate-700 font-medium">
            <UserCheck className="w-4 h-4 text-blue-600" />
            <span>{user?.name || 'Admin'}</span>
          </div>

          <button
            onClick={fetchData}
            className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-white border border-slate-200 text-xs font-bold text-slate-700 hover:bg-slate-50 transition shadow-sm"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            <span>Actualiser</span>
          </button>

          <button
            onClick={logout}
            className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-slate-100 hover:bg-red-50 hover:text-red-700 text-xs font-bold text-slate-600 border border-slate-200 transition"
            title="Se déconnecter"
          >
            <LogOut className="w-3.5 h-3.5" />
            <span className="hidden md:inline">Déconnexion</span>
          </button>
        </div>
      </div>

      {/* KPI Cards - Pure Blue & White */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white p-5 rounded-2xl border border-blue-100 shadow-sm">
          <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">Chiffre d’Affaires</span>
          <div className="text-2xl sm:text-3xl font-black text-blue-900 mt-1">
            {totalRevenue.toFixed(2)} <span className="text-sm font-bold text-slate-500">DT</span>
          </div>
          <span className="text-[10px] text-blue-600 font-semibold">Toutes commandes confondues</span>
        </div>

        <div className="bg-white p-5 rounded-2xl border border-blue-100 shadow-sm">
          <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">Total Commandes</span>
          <div className="text-2xl sm:text-3xl font-black text-slate-900 mt-1">
            {orders.length}
          </div>
          <span className="text-[10px] text-blue-600 font-semibold">{pendingOrders} en attente de traitement</span>
        </div>

        <div className="bg-white p-5 rounded-2xl border border-blue-100 shadow-sm">
          <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">Alertes Stock</span>
          <div className="text-2xl sm:text-3xl font-black text-blue-700 mt-1">
            {lowStockCount}
          </div>
          <span className="text-[10px] text-slate-500 font-semibold">Articles avec stock ≤ 20</span>
        </div>

        <div className="bg-white p-5 rounded-2xl border border-blue-100 shadow-sm">
          <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">Demandes B2B</span>
          <div className="text-2xl sm:text-3xl font-black text-blue-600 mt-1">
            {leads.length}
          </div>
          <span className="text-[10px] text-slate-500 font-semibold">Hôtels &amp; Cliniques en cours</span>
        </div>
      </div>

      {/* Tabs Switcher */}
      <div className="flex border-b border-slate-200 gap-2 overflow-x-auto">
        <button
          onClick={() => setActiveTab('orders')}
          className={`px-5 py-3 text-xs sm:text-sm font-bold border-b-2 flex items-center gap-2 whitespace-nowrap transition ${
            activeTab === 'orders'
              ? 'border-blue-600 text-blue-700'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <ShoppingBag className="w-4 h-4" />
          <span>Commandes Clients ({orders.length})</span>
        </button>

        <button
          onClick={() => setActiveTab('stock')}
          className={`px-5 py-3 text-xs sm:text-sm font-bold border-b-2 flex items-center gap-2 whitespace-nowrap transition ${
            activeTab === 'stock'
              ? 'border-blue-600 text-blue-700'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <Package className="w-4 h-4" />
          <span>Inventaire &amp; Stocks ({products.length})</span>
        </button>

        <button
          onClick={() => setActiveTab('certificates')}
          className={`px-5 py-3 text-xs sm:text-sm font-bold border-b-2 flex items-center gap-2 whitespace-nowrap transition ${
            activeTab === 'certificates'
              ? 'border-blue-600 text-blue-700'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <Award className="w-4 h-4" />
          <span>Certificats &amp; Numéros de Série</span>
        </button>

        <button
          onClick={() => setActiveTab('leads')}
          className={`px-5 py-3 text-xs sm:text-sm font-bold border-b-2 flex items-center gap-2 whitespace-nowrap transition ${
            activeTab === 'leads'
              ? 'border-blue-600 text-blue-700'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <Building2 className="w-4 h-4" />
          <span>Demandes Devis Hôtels &amp; Pro ({leads.length})</span>
        </button>
      </div>

      {/* ============================================================ */}
      {/* TAB 1: COMMANDES */}
      {/* ============================================================ */}
      {activeTab === 'orders' && (
        <div className="bg-white rounded-3xl border border-slate-200 overflow-hidden shadow-sm">
          <div className="p-5 border-b border-slate-200 flex justify-between items-center bg-slate-50">
            <h3 className="font-extrabold text-sm text-slate-900">
              Historique des Commandes en Ligne (Base MySQL)
            </h3>
            <span className="text-xs text-slate-500">Paiement à la livraison / CB</span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="bg-slate-100 text-slate-700 font-bold border-b border-slate-200">
                  <th className="p-3.5">Réf. Commande</th>
                  <th className="p-3.5">Date</th>
                  <th className="p-3.5">Client &amp; Téléphone</th>
                  <th className="p-3.5">Gouvernorat</th>
                  <th className="p-3.5">Articles &amp; Séries</th>
                  <th className="p-3.5 text-right">Total Net</th>
                  <th className="p-3.5">Statut</th>
                  <th className="p-3.5 text-center">Garantie &amp; Certificat</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {orders.map((order) => (
                  <tr key={order.id} className="hover:bg-slate-50/70 transition">
                    <td className="p-3.5 font-bold font-mono text-blue-800">
                      {order.id}
                    </td>
                    <td className="p-3.5 text-slate-500 whitespace-nowrap">
                      {new Date(order.date).toLocaleDateString('fr-TN', {
                        day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit'
                      })}
                    </td>
                    <td className="p-3.5">
                      <div className="font-bold text-slate-900">{order.customer?.fullName}</div>
                      <div className="text-slate-500 font-mono text-[11px]">{order.customer?.phone}</div>
                    </td>
                    <td className="p-3.5 font-semibold text-slate-700">
                      {order.customer?.governorate || order.customer?.city}
                    </td>
                    <td className="p-3.5 max-w-xs">
                      {order.items?.map((it, idx) => (
                        <div key={idx} className="truncate text-slate-700">
                          <strong className="text-slate-900">{it.quantity}x</strong> {it.name}
                        </div>
                      ))}
                    </td>
                    <td className="p-3.5 text-right font-black text-blue-900 whitespace-nowrap">
                      {order.total?.toFixed(2)} DT
                    </td>
                    <td className="p-3.5">
                      <select
                        value={order.status}
                        onChange={(e) => handleUpdateOrderStatus(order.id, e.target.value)}
                        className={`px-2.5 py-1 rounded-lg text-[11px] font-bold border outline-none ${
                          order.status === 'delivered'
                            ? 'bg-blue-100 text-blue-900 border-blue-300'
                            : order.status === 'shipped'
                            ? 'bg-sky-50 text-sky-800 border-sky-300'
                            : order.status === 'confirmed'
                            ? 'bg-blue-50 text-blue-800 border-blue-300'
                            : 'bg-slate-100 text-slate-700 border-slate-300'
                        }`}
                      >
                        <option value="pending">En attente</option>
                        <option value="confirmed">Confirmée</option>
                        <option value="shipped">Expédiée (Livreur)</option>
                        <option value="delivered">Livrée &amp; Payée</option>
                        <option value="cancelled">Annulée</option>
                      </select>
                    </td>
                    <td className="p-3.5 text-center">
                      <button
                        onClick={() => handleViewCertificate(order.id)}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-blue-50 hover:bg-blue-100 text-blue-800 font-bold text-[11px] border border-blue-200 transition"
                      >
                        <Award className="w-3.5 h-3.5 text-blue-600" />
                        <span>Voir Certificat</span>
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ============================================================ */}
      {/* TAB 2: INVENTAIRE & STOCKS */}
      {/* ============================================================ */}
      {activeTab === 'stock' && (
        <div className="bg-white rounded-3xl border border-slate-200 overflow-hidden shadow-sm">
          <div className="p-5 border-b border-slate-200 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3 bg-slate-50">
            <div>
              <h3 className="font-extrabold text-sm text-slate-900">
                Gestion des Produits, Prix &amp; Quantités en Stock (MySQL)
              </h3>
              <span className="text-xs text-slate-500">Mise à jour en temps réel</span>
            </div>

            <button
              onClick={() => setShowAddProductModal(true)}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-xs font-bold flex items-center space-x-1.5 shadow-sm transition-colors"
            >
              <Plus className="w-4 h-4" />
              <span>Nouveau Produit</span>
            </button>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="bg-slate-100 text-slate-700 font-bold border-b border-slate-200">
                  <th className="p-3.5">Produit</th>
                  <th className="p-3.5">Catégorie</th>
                  <th className="p-3.5">Débit</th>
                  <th className="p-3.5">Prix HT / Vente (DT)</th>
                  <th className="p-3.5">Stock Disponible</th>
                  <th className="p-3.5 text-center">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {products.map((prod) => {
                  const isEditing = editingProduct === prod.id;
                  return (
                    <tr key={prod.id} className="hover:bg-slate-50/70 transition">
                      <td className="p-3.5 flex items-center gap-3">
                        <img
                          src={prod.image}
                          alt={prod.name}
                          className="w-10 h-10 rounded-lg object-cover border border-slate-200 shrink-0 bg-slate-50"
                        />
                        <div>
                          <div className="font-bold text-slate-900">{prod.name}</div>
                          <div className="text-[10px] text-slate-400 font-mono">{prod.id}</div>
                        </div>
                      </td>
                      <td className="p-3.5 capitalize font-semibold text-slate-600">
                        {prod.category}
                      </td>
                      <td className="p-3.5 font-bold text-blue-700">
                        {prod.debit || '—'}
                      </td>
                      <td className="p-3.5">
                        {isEditing ? (
                          <input
                            type="number"
                            step="0.1"
                            value={editPrice}
                            onChange={(e) => setEditPrice(e.target.value)}
                            className="w-24 px-2 py-1 border border-blue-500 rounded-md font-bold text-slate-900"
                          />
                        ) : (
                          <span className="font-extrabold text-slate-900 text-sm">
                            {prod.price.toFixed(2)} DT
                          </span>
                        )}
                      </td>
                      <td className="p-3.5">
                        {isEditing ? (
                          <input
                            type="number"
                            value={editStock}
                            onChange={(e) => setEditStock(e.target.value)}
                            className="w-20 px-2 py-1 border border-blue-500 rounded-md font-bold text-slate-900"
                          />
                        ) : (
                          <span className={`px-2.5 py-1 rounded-full font-bold text-[11px] ${
                            prod.stock <= 20
                              ? 'bg-red-50 text-red-700 border border-red-200'
                              : 'bg-blue-50 text-blue-800'
                          }`}>
                            {prod.stock} unités
                          </span>
                        )}
                      </td>
                      <td className="p-3.5 text-center">
                        <div className="flex items-center justify-center space-x-1.5">
                          {isEditing ? (
                            <button
                              onClick={() => handleSaveProduct(prod.id)}
                              className="inline-flex items-center gap-1 px-3 py-1.5 rounded-xl bg-blue-600 text-white font-bold text-xs shadow-xs hover:bg-blue-700"
                            >
                              <Save className="w-3.5 h-3.5" />
                              <span>Enregistrer</span>
                            </button>
                          ) : (
                            <button
                              onClick={() => {
                                setEditingProduct(prod.id);
                                setEditPrice(prod.price.toString());
                                setEditStock(prod.stock.toString());
                              }}
                              className="inline-flex items-center gap-1 px-3 py-1.5 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold text-xs"
                            >
                              <Edit3 className="w-3.5 h-3.5" />
                              <span>Modifier</span>
                            </button>
                          )}
                          <button
                            onClick={() => handleDeleteProduct(prod.id)}
                            className="p-1.5 rounded-xl bg-slate-100 hover:bg-red-50 hover:text-red-600 text-slate-400 transition"
                            title="Supprimer le produit"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ============================================================ */}
      {/* TAB 3: CERTIFICATS & NUMÉROS DE SÉRIE */}
      {/* ============================================================ */}
      {activeTab === 'certificates' && (
        <div className="space-y-6">
          <div className="bg-white rounded-3xl p-6 border border-slate-200 shadow-sm flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
            <div>
              <h3 className="font-extrabold text-slate-900 text-base">
                Registre des Certificats de Garantie &amp; Numéros de Série Émis
              </h3>
              <p className="text-xs text-slate-500 mt-0.5">
                Chaque pièce vendue possède un numéro d'agrément officiel Delrin/Hostaform garanti 3 ans.
              </p>
            </div>

            <div className="relative w-full sm:w-72">
              <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                value={searchSerial}
                onChange={(e) => setSearchSerial(e.target.value)}
                placeholder="Rechercher numéro de série..."
                className="w-full pl-9 pr-3 py-2 rounded-xl border border-slate-200 text-xs focus:border-blue-500 outline-none"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {filteredOrdersForCertificates.map((ord) => (
              <div
                key={ord.id}
                className="bg-white rounded-2xl border border-blue-100 p-5 shadow-sm flex flex-col justify-between space-y-4 hover:border-blue-300 transition"
              >
                <div>
                  <div className="flex justify-between items-start">
                    <span className="font-mono text-xs font-black text-blue-800 bg-blue-50 px-2 py-0.5 rounded-md">
                      {ord.certificateSerial || `CERT-2026-${ord.id}`}
                    </span>
                    <span className="text-[10px] font-bold text-blue-700 bg-blue-100 px-2 py-0.5 rounded-full">
                      Valide 3 ans
                    </span>
                  </div>

                  <h4 className="font-bold text-sm text-slate-900 mt-3">
                    {ord.customer?.fullName}
                  </h4>
                  <p className="text-xs text-slate-500">{ord.customer?.city} ({ord.customer?.governorate})</p>

                  <div className="mt-3 space-y-1 pt-3 border-t border-slate-100 text-xs">
                    <span className="text-[10px] text-slate-400 uppercase font-bold block">Numéros de série gravés :</span>
                    {ord.items?.map((it, idx) => (
                      <div key={idx} className="font-mono text-[11px] text-slate-700 truncate">
                        • {it.serials?.join(', ') || `SN-${ord.id}-${idx}`} ({it.name})
                      </div>
                    ))}
                  </div>
                </div>

                <button
                  onClick={() => handleViewCertificate(ord.id)}
                  className="w-full bg-blue-600 hover:bg-blue-700 text-white py-2 px-3 rounded-xl text-xs font-bold flex items-center justify-center gap-1.5 shadow-sm transition"
                >
                  <Printer className="w-3.5 h-3.5" />
                  <span>Imprimer le Certificat Officiel</span>
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ============================================================ */}
      {/* TAB 4: DEMANDES DEVIS B2B */}
      {/* ============================================================ */}
      {activeTab === 'leads' && (
        <div className="bg-white rounded-3xl border border-slate-200 overflow-hidden shadow-sm">
          <div className="p-5 border-b border-slate-200 flex justify-between items-center bg-slate-50">
            <h3 className="font-extrabold text-sm text-slate-900">
              Demandes de Devis &amp; d'Audits Professionnels (Hôtels &amp; Cliniques)
            </h3>
            <span className="text-xs text-slate-500">Service Technico-Commercial</span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="bg-slate-100 text-slate-700 font-bold border-b border-slate-200">
                  <th className="p-3.5">Établissement</th>
                  <th className="p-3.5">Secteur</th>
                  <th className="p-3.5">Contact &amp; Fonction</th>
                  <th className="p-3.5">Téléphone / Email</th>
                  <th className="p-3.5">Chambres / Facture</th>
                  <th className="p-3.5">Précisions &amp; Objet</th>
                  <th className="p-3.5">Statut</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {leads.map((lead) => (
                  <tr key={lead.id} className="hover:bg-slate-50/70 transition">
                    <td className="p-3.5 font-bold text-slate-900">
                      {lead.company}
                    </td>
                    <td className="p-3.5 capitalize font-semibold text-blue-700">
                      {lead.type}
                    </td>
                    <td className="p-3.5">
                      <div className="font-bold text-slate-800">{lead.contactPerson}</div>
                      <div className="text-[11px] text-slate-500">{lead.role}</div>
                    </td>
                    <td className="p-3.5 font-mono">
                      <div>{lead.phone}</div>
                      <div className="text-slate-500 text-[11px]">{lead.email}</div>
                    </td>
                    <td className="p-3.5">
                      <div>{lead.roomsCount ? `${lead.roomsCount} chambres` : 'Non spécifié'}</div>
                      <div className="text-blue-700 font-bold text-[11px]">
                        {lead.currentWaterBillMonthly || '—'}
                      </div>
                    </td>
                    <td className="p-3.5 max-w-xs text-slate-600">
                      {lead.notes || lead.interest}
                    </td>
                    <td className="p-3.5">
                      <select
                        value={lead.status}
                        onChange={(e) => handleUpdateLeadStatus(lead.id, e.target.value)}
                        className={`px-2.5 py-1 rounded-lg text-[10px] font-bold uppercase tracking-wider border outline-none ${
                          lead.status === 'closed'
                            ? 'bg-slate-100 text-slate-700 border-slate-300'
                            : lead.status === 'in_progress'
                            ? 'bg-blue-100 text-blue-800 border-blue-300'
                            : 'bg-blue-50 text-blue-700 border-blue-200'
                        }`}
                      >
                        <option value="new">Nouveau Devis</option>
                        <option value="in_progress">En Cours / Contacté</option>
                        <option value="closed">Traité / Conclu</option>
                      </select>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Warranty Certificate Modal */}
      {selectedCertificate && (
        <WarrantyCertificateModal
          certificate={selectedCertificate}
          onClose={() => setSelectedCertificate(null)}
        />
      )}

      {/* Add Product Modal */}
      {showAddProductModal && (
        <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-3xl max-w-lg w-full p-6 shadow-2xl border border-blue-100 space-y-4">
            <div className="flex justify-between items-center border-b pb-3">
              <h3 className="font-extrabold text-slate-900 text-lg">Ajouter un Nouveau Produit</h3>
              <button onClick={() => setShowAddProductModal(false)} className="text-slate-400 hover:text-slate-600 font-bold text-lg">✕</button>
            </div>

            <form onSubmit={handleCreateProduct} className="space-y-3">
              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">Nom du Produit (FR)</label>
                <input
                  type="text"
                  required
                  value={newProd.name}
                  onChange={(e) => setNewProd({ ...newProd, name: e.target.value })}
                  placeholder="Ex: Mousseur Aérateur 4L"
                  className="w-full px-3 py-2 border rounded-xl text-sm"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-bold text-slate-700 mb-1">Prix Vente (DT)</label>
                  <input
                    type="number"
                    step="0.1"
                    required
                    value={newProd.price}
                    onChange={(e) => setNewProd({ ...newProd, price: e.target.value })}
                    placeholder="25.0"
                    className="w-full px-3 py-2 border rounded-xl text-sm"
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold text-slate-700 mb-1">Stock Initial</label>
                  <input
                    type="number"
                    required
                    value={newProd.stock}
                    onChange={(e) => setNewProd({ ...newProd, stock: e.target.value })}
                    className="w-full px-3 py-2 border rounded-xl text-sm"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-bold text-slate-700 mb-1">Catégorie</label>
                  <select
                    value={newProd.category}
                    onChange={(e) => setNewProd({ ...newProd, category: e.target.value })}
                    className="w-full px-3 py-2 border rounded-xl text-sm"
                  >
                    <option value="packs">Packs</option>
                    <option value="robinets">Robinets</option>
                    <option value="douches">Douches</option>
                    <option value="accessoires">Accessoires</option>
                    <option value="energie">Énergie</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-bold text-slate-700 mb-1">Débit calibré</label>
                  <input
                    type="text"
                    value={newProd.debit}
                    onChange={(e) => setNewProd({ ...newProd, debit: e.target.value })}
                    placeholder="4 L/min"
                    className="w-full px-3 py-2 border rounded-xl text-sm"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">Description</label>
                <textarea
                  rows={2}
                  value={newProd.description}
                  onChange={(e) => setNewProd({ ...newProd, description: e.target.value })}
                  placeholder="Caractéristiques techniques et avantages..."
                  className="w-full px-3 py-2 border rounded-xl text-sm"
                />
              </div>

              <div className="flex justify-end space-x-2 pt-2 border-t">
                <button
                  type="button"
                  onClick={() => setShowAddProductModal(false)}
                  className="px-4 py-2 bg-slate-100 text-slate-700 text-xs font-bold rounded-xl"
                >
                  Annuler
                </button>
                <button
                  type="submit"
                  className="px-5 py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold rounded-xl shadow-md"
                >
                  Enregistrer dans MySQL
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

    </div>
  );
};
