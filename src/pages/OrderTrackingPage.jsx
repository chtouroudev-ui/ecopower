import React, { useState, useEffect } from 'react';
import { Search, Package, CheckCircle2, Clock, Truck, ShieldCheck, ArrowRight, FileText, User } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { WarrantyCertificateModal } from '../components/WarrantyCertificateModal';

export function OrderTrackingPage() {
  const { user, isAuthenticated, token, openLogin } = useAuth();
  const [searchQuery, setSearchQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState(null);
  const [error, setError] = useState(null);

  const [userOrders, setUserOrders] = useState([]);
  const [loadingUserOrders, setLoadingUserOrders] = useState(false);

  // Certificate Modal
  const [selectedOrderId, setSelectedOrderId] = useState(null);

  // Fetch logged in user's orders automatically
  useEffect(() => {
    if (isAuthenticated && token) {
      setLoadingUserOrders(true);
      fetch('/api/user/orders', {
        headers: { Authorization: `Bearer ${token}` }
      })
        .then(res => res.json())
        .then(data => {
          if (Array.isArray(data)) {
            setUserOrders(data);
          }
        })
        .catch(console.error)
        .finally(() => setLoadingUserOrders(false));
    }
  }, [isAuthenticated, token]);

  const handleSearch = async (e) => {
    e.preventDefault();
    if (!searchQuery.trim()) return;

    setError(null);
    setLoading(true);
    setResults(null);

    try {
      const res = await fetch(`/api/orders/track/${encodeURIComponent(searchQuery.trim())}`);
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.error || 'Aucune commande trouvée.');
      }
      setResults(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const getStatusBadge = (status) => {
    switch (status) {
      case 'delivered':
        return (
          <span className="inline-flex items-center space-x-1 px-3 py-1 bg-blue-100 text-blue-800 text-xs font-bold rounded-full">
            <CheckCircle2 className="w-3.5 h-3.5 text-blue-600" />
            <span>Livrée</span>
          </span>
        );
      case 'shipped':
        return (
          <span className="inline-flex items-center space-x-1 px-3 py-1 bg-blue-100 text-blue-700 text-xs font-bold rounded-full">
            <Truck className="w-3.5 h-3.5 text-blue-600" />
            <span>En cours de livraison</span>
          </span>
        );
      case 'confirmed':
        return (
          <span className="inline-flex items-center space-x-1 px-3 py-1 bg-sky-100 text-sky-800 text-xs font-bold rounded-full">
            <CheckCircle2 className="w-3.5 h-3.5 text-sky-600" />
            <span>Confirmée &amp; Préparée</span>
          </span>
        );
      case 'cancelled':
        return (
          <span className="inline-flex items-center space-x-1 px-3 py-1 bg-slate-100 text-slate-700 text-xs font-bold rounded-full">
            <span>Annulée</span>
          </span>
        );
      case 'pending':
      default:
        return (
          <span className="inline-flex items-center space-x-1 px-3 py-1 bg-blue-50 text-blue-700 border border-blue-200 text-xs font-bold rounded-full">
            <Clock className="w-3.5 h-3.5 text-blue-600" />
            <span>En attente de confirmation</span>
          </span>
        );
    }
  };

  return (
    <div className="py-12 max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 space-y-10">
      {/* Header */}
      <div className="text-center max-w-2xl mx-auto space-y-3">
        <div className="inline-flex items-center space-x-2 px-3 py-1 rounded-full bg-blue-50 border border-blue-200 text-blue-800 text-xs font-bold tracking-wide">
          <Truck className="w-3.5 h-3.5 text-blue-600" />
          <span>Suivi en temps réel &amp; Certificat Officiel</span>
        </div>
        <h1 className="text-3xl sm:text-4xl font-black text-slate-900 font-serif">
          Suivi de Commande &amp; Garantie
        </h1>
        <p className="text-slate-600 text-sm">
          Saisissez votre référence de commande (ex: <code className="bg-slate-100 px-1 py-0.5 rounded text-blue-700 font-bold">ECO-1006</code>) ou votre numéro de téléphone pour vérifier l'état d'expédition et télécharger votre certificat de garantie 3 ans.
        </p>
      </div>

      {/* Search Bar */}
      <div className="max-w-2xl mx-auto bg-white p-3 rounded-2xl shadow-xl shadow-blue-900/5 border border-blue-100">
        <form onSubmit={handleSearch} className="flex flex-col sm:flex-row gap-2">
          <div className="relative flex-1">
            <Search className="w-5 h-5 text-slate-400 absolute left-4 top-3.5" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Ex: ECO-1006 ou 22334455"
              className="w-full pl-12 pr-4 py-3 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-blue-600 focus:bg-white text-slate-900 font-medium transition-all"
            />
          </div>
          <button
            type="submit"
            disabled={loading}
            className="px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white font-bold rounded-xl shadow-md shadow-blue-500/25 flex items-center justify-center space-x-2 transition-all disabled:opacity-50"
          >
            {loading ? (
              <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
            ) : (
              <>
                <span>Vérifier</span>
                <ArrowRight className="w-4 h-4" />
              </>
            )}
          </button>
        </form>
      </div>

      {/* Error notification */}
      {error && (
        <div className="max-w-2xl mx-auto p-4 bg-red-50 border border-red-200 rounded-xl text-red-700 text-sm flex items-center justify-between">
          <span>{error}</span>
          <button onClick={() => setError(null)} className="text-red-500 hover:text-red-800 font-bold text-xs">Fermer</button>
        </div>
      )}

      {/* Search Results Display */}
      {results && results.length > 0 && (
        <div className="space-y-6">
          <h2 className="text-xl font-bold text-slate-900 flex items-center space-x-2">
            <Package className="w-5 h-5 text-blue-600" />
            <span>Résultats ({results.length})</span>
          </h2>

          <div className="grid gap-6">
            {results.map((order) => (
              <div
                key={order.id}
                className="bg-white rounded-2xl border border-blue-100 shadow-md p-6 space-y-6"
              >
                <div className="flex flex-wrap items-center justify-between gap-4 pb-4 border-b border-slate-100">
                  <div>
                    <span className="text-xs font-bold text-blue-600 tracking-wider">RÉFÉRENCE</span>
                    <h3 className="text-2xl font-black text-slate-900">{order.id}</h3>
                    <p className="text-xs text-slate-500">
                      Passée le {new Date(order.date).toLocaleDateString('fr-TN', { day: 'numeric', month: 'long', year: 'numeric' })}
                    </p>
                  </div>
                  <div className="text-right flex flex-col items-end gap-2">
                    {getStatusBadge(order.status)}
                    <span className="text-xl font-extrabold text-slate-900 font-mono">
                      {order.total.toFixed(2)} DT
                    </span>
                  </div>
                </div>

                {/* Tracking Progress Steps */}
                <div className="py-2">
                  <div className="grid grid-cols-4 gap-2 text-center text-xs">
                    <div className="space-y-2">
                      <div className="w-8 h-8 mx-auto rounded-full bg-blue-600 text-white flex items-center justify-center font-bold">
                        1
                      </div>
                      <span className="font-bold text-slate-800">Reçue</span>
                    </div>
                    <div className="space-y-2">
                      <div className={`w-8 h-8 mx-auto rounded-full flex items-center justify-center font-bold ${
                        ['confirmed', 'shipped', 'delivered'].includes(order.status)
                          ? 'bg-blue-600 text-white'
                          : 'bg-slate-100 text-slate-400'
                      }`}>
                        2
                      </div>
                      <span className={`font-semibold ${['confirmed', 'shipped', 'delivered'].includes(order.status) ? 'text-slate-800' : 'text-slate-400'}`}>
                        Confirmée
                      </span>
                    </div>
                    <div className="space-y-2">
                      <div className={`w-8 h-8 mx-auto rounded-full flex items-center justify-center font-bold ${
                        ['shipped', 'delivered'].includes(order.status)
                          ? 'bg-blue-600 text-white'
                          : 'bg-slate-100 text-slate-400'
                      }`}>
                        3
                      </div>
                      <span className={`font-semibold ${['shipped', 'delivered'].includes(order.status) ? 'text-slate-800' : 'text-slate-400'}`}>
                        En livraison
                      </span>
                    </div>
                    <div className="space-y-2">
                      <div className={`w-8 h-8 mx-auto rounded-full flex items-center justify-center font-bold ${
                        order.status === 'delivered'
                          ? 'bg-blue-600 text-white'
                          : 'bg-slate-100 text-slate-400'
                      }`}>
                        4
                      </div>
                      <span className={`font-semibold ${order.status === 'delivered' ? 'text-slate-800' : 'text-slate-400'}`}>
                        Livrée
                      </span>
                    </div>
                  </div>
                </div>

                {/* Items & Serials */}
                <div className="bg-slate-50 p-4 rounded-xl border border-slate-100 space-y-3">
                  <h4 className="text-xs font-bold text-slate-600 uppercase tracking-wider">
                    Articles &amp; Numéros de Série Certifiés
                  </h4>
                  <div className="space-y-2">
                    {order.items.map((item, idx) => (
                      <div key={idx} className="flex flex-col sm:flex-row sm:items-center justify-between text-sm py-1.5 border-b border-slate-200/60 last:border-0">
                        <span className="font-semibold text-slate-800">
                          {item.quantity}x {item.name}
                        </span>
                        {item.serials && item.serials.length > 0 && (
                          <div className="flex flex-wrap gap-1 mt-1 sm:mt-0">
                            {item.serials.map((s, sIdx) => (
                              <span key={sIdx} className="px-2 py-0.5 bg-blue-100/80 text-blue-800 text-[11px] font-mono rounded font-semibold">
                                {s}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>

                {/* Action button */}
                <div className="flex justify-end pt-2">
                  <button
                    onClick={() => setSelectedOrderId(order.id)}
                    className="inline-flex items-center space-x-2 px-5 py-2.5 bg-blue-600 hover:bg-blue-700 text-white font-bold text-sm rounded-xl shadow-md transition-colors"
                  >
                    <ShieldCheck className="w-4 h-4" />
                    <span>Consulter le Certificat de Garantie</span>
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Logged in User's Orders Section */}
      {isAuthenticated ? (
        <div className="pt-8 border-t border-slate-200 space-y-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <div className="w-10 h-10 rounded-full bg-blue-100 text-blue-700 flex items-center justify-center font-bold">
                <User className="w-5 h-5" />
              </div>
              <div>
                <h2 className="text-xl font-bold text-slate-900">Historique de vos commandes</h2>
                <p className="text-xs text-slate-500">Connecté en tant que {user?.name} ({user?.email})</p>
              </div>
            </div>
          </div>

          {loadingUserOrders ? (
            <div className="text-center py-8 text-slate-500 text-sm">Chargement de vos commandes...</div>
          ) : userOrders.length > 0 ? (
            <div className="grid gap-4">
              {userOrders.map((ord) => (
                <div key={ord.id} className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
                  <div>
                    <div className="flex items-center space-x-3">
                      <span className="font-extrabold text-blue-700 text-lg">{ord.id}</span>
                      {getStatusBadge(ord.status)}
                    </div>
                    <p className="text-xs text-slate-500 mt-1">
                      {new Date(ord.date).toLocaleDateString('fr-TN')} • {ord.items.length} article(s) • Livré à {ord.customer.city || ord.customer.governorate}
                    </p>
                  </div>
                  <div className="flex items-center space-x-4">
                    <span className="font-bold text-slate-900 text-lg font-mono">{ord.total.toFixed(2)} DT</span>
                    <button
                      onClick={() => setSelectedOrderId(ord.id)}
                      className="px-4 py-2 bg-blue-50 hover:bg-blue-100 text-blue-700 border border-blue-200 rounded-xl text-xs font-bold flex items-center space-x-1.5 transition-colors"
                    >
                      <FileText className="w-3.5 h-3.5 text-blue-600" />
                      <span>Certificat</span>
                    </button>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-8 bg-slate-50 rounded-2xl border border-dashed border-slate-200 text-slate-500 text-sm">
              Vous n'avez pas encore passé de commande avec ce compte.
            </div>
          )}
        </div>
      ) : (
        <div className="bg-blue-50 border border-blue-200 rounded-2xl p-6 text-center space-y-3">
          <h3 className="text-lg font-bold text-blue-900">Vous avez déjà un compte EcoPower ?</h3>
          <p className="text-xs text-blue-700 max-w-md mx-auto">
            Connectez-vous pour retrouver automatiquement toutes vos commandes, factures et certificats de garantie sans avoir à taper votre référence.
          </p>
          <button
            onClick={openLogin}
            className="px-6 py-2.5 bg-blue-600 hover:bg-blue-700 text-white font-bold text-xs rounded-xl shadow-md transition-colors"
          >
            Se connecter à mon compte
          </button>
        </div>
      )}

      {/* Warranty Certificate Modal */}
      {selectedOrderId && (
        <WarrantyCertificateModal
          orderId={selectedOrderId}
          onClose={() => setSelectedOrderId(null)}
        />
      )}
    </div>
  );
}
