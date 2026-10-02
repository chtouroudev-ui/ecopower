import React, { useState, useEffect } from 'react';
import { WarrantyCertificateModal } from '../components/WarrantyCertificateModal';
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
  Minus, 
  Search,
  RefreshCw,
  Eye
} from 'lucide-react';

export const AdminDashboard = () => {
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

  const fetchData = async () => {
    setLoading(true);
    try {
      const [ordRes, prodRes, leadRes] = await Promise.all([
        fetch('/api/orders').then(r => r.json()),
        fetch('/api/products').then(r => r.json()),
        fetch('/api/leads').then(r => r.json())
      ]);
      setOrders(ordRes);
      setProducts(prodRes);
      setLeads(leadRes);
    } catch (err) {
      console.error('Error fetching admin data:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

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

  const handleSaveProduct = async (productId) => {
    try {
      const res = await fetch(`/api/products/${productId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          price: parseFloat(editPrice),
          stock: parseInt(editStock, 10)
        })
      });
      if (res.ok) {
        const updated = await res.json();
        setProducts(products.map(p => p.id === productId ? updated : p));
        setEditingProduct(null);
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

  // KPIs
  const totalRevenue = orders.reduce((sum, o) => sum + (o.total || 0), 0);
  const pendingOrders = orders.filter(o => o.status === 'pending').length;
  const lowStockCount = products.filter(p => (p.stock || 0) <= 20).length;

  return (
    <div className="py-8 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-8">
      
      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center pb-6 border-b border-slate-200 gap-4">
        <div>
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-brand-100 text-brand-800 text-xs font-bold uppercase tracking-wider mb-1">
            <LayoutDashboard className="w-3.5 h-3.5" />
            <span>Panneau de Contrôle Directeur</span>
          </div>
          <h1 className="text-3xl font-extrabold text-slate-900 font-serif">
            Interface d'Administration EcoPower
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Gestion des commandes, suivi des stocks, et émission des certificats de garantie officiels avec numéros de série.
          </p>
        </div>

        <button
          onClick={fetchData}
          className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-white border border-slate-200 text-xs font-bold text-slate-700 hover:bg-slate-50 transition shadow-2xs"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          <span>Actualiser</span>
        </button>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-2xs">
          <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">Chiffre d’Affaires</span>
          <div className="text-2xl sm:text-3xl font-black text-brand-900 mt-1">
            {totalRevenue.toFixed(3)} <span className="text-sm font-bold text-slate-500">DT</span>
          </div>
          <span className="text-[10px] text-emerald-600 font-semibold">Toutes commandes confondues</span>
        </div>

        <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-2xs">
          <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">Total Commandes</span>
          <div className="text-2xl sm:text-3xl font-black text-slate-900 mt-1">
            {orders.length}
          </div>
          <span className="text-[10px] text-brand-600 font-semibold">{pendingOrders} en attente de traitement</span>
        </div>

        <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-2xs">
          <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">Alertes Stock</span>
          <div className="text-2xl sm:text-3xl font-black text-amber-600 mt-1">
            {lowStockCount}
          </div>
          <span className="text-[10px] text-amber-700 font-semibold">Articles avec stock ≤ 20</span>
        </div>

        <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-2xs">
          <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">Demandes B2B</span>
          <div className="text-2xl sm:text-3xl font-black text-skywater-600 mt-1">
            {leads.length}
          </div>
          <span className="text-[10px] text-skywater-700 font-semibold">Hôtels &amp; Cliniques en cours</span>
        </div>
      </div>

      {/* Tabs Switcher */}
      <div className="flex border-b border-slate-200 gap-2 overflow-x-auto">
        <button
          onClick={() => setActiveTab('orders')}
          className={`px-5 py-3 text-xs sm:text-sm font-bold border-b-2 flex items-center gap-2 whitespace-nowrap transition ${
            activeTab === 'orders'
              ? 'border-brand-700 text-brand-800'
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
              ? 'border-brand-700 text-brand-800'
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
              ? 'border-brand-700 text-brand-800'
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
              ? 'border-brand-700 text-brand-800'
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
        <div className="bg-white rounded-3xl border border-slate-200 overflow-hidden shadow-2xs">
          <div className="p-5 border-b border-slate-200 flex justify-between items-center bg-slate-50">
            <h3 className="font-extrabold text-sm text-slate-900">
              Historique des Commandes en Ligne
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
                  <th className="p-3.5">Articles Commandés</th>
                  <th className="p-3.5 text-right">Total Net</th>
                  <th className="p-3.5">Statut</th>
                  <th className="p-3.5 text-center">Garantie &amp; Certificat</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {orders.map((order) => (
                  <tr key={order.id} className="hover:bg-slate-50/70 transition">
                    <td className="p-3.5 font-bold font-mono text-brand-900">
                      {order.id}
                    </td>
                    <td className="p-3.5 text-slate-500 whitespace-nowrap">
                      {new Date(order.date).toLocaleDateString('fr-FR', {
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
                    <td className="p-3.5 text-right font-black text-brand-900 whitespace-nowrap">
                      {order.total?.toFixed(3)} DT
                    </td>
                    <td className="p-3.5">
                      <select
                        value={order.status}
                        onChange={(e) => handleUpdateOrderStatus(order.id, e.target.value)}
                        className={`px-2.5 py-1 rounded-lg text-[11px] font-bold border outline-none ${
                          order.status === 'delivered'
                            ? 'bg-emerald-50 text-emerald-800 border-emerald-300'
                            : order.status === 'shipped'
                            ? 'bg-skywater-50 text-skywater-800 border-skywater-300'
                            : order.status === 'confirmed'
                            ? 'bg-brand-50 text-brand-800 border-brand-300'
                            : 'bg-amber-50 text-amber-800 border-amber-300'
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
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-brand-50 hover:bg-brand-100 text-brand-800 font-bold text-[11px] border border-brand-200 transition"
                      >
                        <Award className="w-3.5 h-3.5 text-brand-600" />
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
        <div className="bg-white rounded-3xl border border-slate-200 overflow-hidden shadow-2xs">
          <div className="p-5 border-b border-slate-200 flex justify-between items-center bg-slate-50">
            <h3 className="font-extrabold text-sm text-slate-900">
              Gestion des Produits, Prix &amp; Quantités en Stock
            </h3>
            <span className="text-xs text-slate-500">Mise à jour en temps réel</span>
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
                      <td className="p-3.5 font-bold text-brand-700">
                        {prod.debit || '—'}
                      </td>
                      <td className="p-3.5">
                        {isEditing ? (
                          <input
                            type="number"
                            step="0.1"
                            value={editPrice}
                            onChange={(e) => setEditPrice(e.target.value)}
                            className="w-24 px-2 py-1 border border-brand-500 rounded-md font-bold"
                          />
                        ) : (
                          <span className="font-extrabold text-slate-900 text-sm">
                            {prod.price.toFixed(3)} DT
                          </span>
                        )}
                      </td>
                      <td className="p-3.5">
                        {isEditing ? (
                          <input
                            type="number"
                            value={editStock}
                            onChange={(e) => setEditStock(e.target.value)}
                            className="w-20 px-2 py-1 border border-brand-500 rounded-md font-bold"
                          />
                        ) : (
                          <span className={`px-2.5 py-1 rounded-full font-bold text-[11px] ${
                            prod.stock <= 20
                              ? 'bg-red-50 text-red-700 border border-red-200'
                              : 'bg-emerald-50 text-emerald-800'
                          }`}>
                            {prod.stock} unités
                          </span>
                        )}
                      </td>
                      <td className="p-3.5 text-center">
                        {isEditing ? (
                          <button
                            onClick={() => handleSaveProduct(prod.id)}
                            className="inline-flex items-center gap-1 px-3 py-1.5 rounded-xl bg-emerald-600 text-white font-bold text-xs shadow-xs hover:bg-emerald-700"
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
          <div className="bg-white rounded-3xl p-6 border border-slate-200 shadow-2xs flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
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
                className="w-full pl-9 pr-3 py-2 rounded-xl border border-slate-200 text-xs focus:border-brand-500 outline-none"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {orders.map((ord) => (
              <div
                key={ord.id}
                className="bg-white rounded-2xl border border-slate-200 p-5 shadow-xs flex flex-col justify-between space-y-4 hover:border-brand-300 transition"
              >
                <div>
                  <div className="flex justify-between items-start">
                    <span className="font-mono text-xs font-black text-brand-800 bg-brand-50 px-2 py-0.5 rounded-md">
                      {ord.certificateSerial || `CERT-2026-${ord.id}`}
                    </span>
                    <span className="text-[10px] font-bold text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded-full">
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
                  className="w-full bg-brand-700 hover:bg-brand-800 text-white py-2 px-3 rounded-xl text-xs font-bold flex items-center justify-center gap-1.5 shadow-xs transition"
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
        <div className="bg-white rounded-3xl border border-slate-200 overflow-hidden shadow-2xs">
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
                    <td className="p-3.5 capitalize font-semibold text-brand-700">
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
                      <div className="text-emerald-700 font-bold text-[11px]">
                        {lead.currentWaterBillMonthly || '—'}
                      </div>
                    </td>
                    <td className="p-3.5 max-w-xs text-slate-600">
                      {lead.notes || lead.interest}
                    </td>
                    <td className="p-3.5">
                      <span className={`px-2.5 py-1 rounded-full font-bold text-[10px] uppercase tracking-wider ${
                        lead.status === 'closed'
                          ? 'bg-slate-100 text-slate-700'
                          : lead.status === 'in_progress'
                          ? 'bg-skywater-50 text-skywater-800'
                          : 'bg-emerald-50 text-emerald-800'
                      }`}>
                        {lead.status === 'new' ? 'Nouveau Devis' : lead.status === 'in_progress' ? 'En Cours' : 'Traité'}
                      </span>
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

    </div>
  );
};
