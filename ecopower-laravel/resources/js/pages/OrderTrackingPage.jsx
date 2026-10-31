import React, { useState, useEffect } from 'react';
import { Search, Package, CheckCircle2, Clock, Truck, ShieldCheck, ArrowRight, CreditCard, Store, Loader2 } from 'lucide-react';
import { WarrantyCertificateModal } from '../components/WarrantyCertificateModal';
import { useCart } from '../context/CartContext';

export function OrderTrackingPage({ initialQuery = '' }) {
  const { pickupInfo } = useCart();
  const [searchQuery, setSearchQuery] = useState(() => {
    if (initialQuery) return initialQuery;
    try {
      return localStorage.getItem('ecopower_last_order') || '';
    } catch {
      return '';
    }
  });
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState(null);
  const [error, setError] = useState(null);

  // Certificate Modal
  const [selectedOrderId, setSelectedOrderId] = useState(null);

  const runSearch = async (query) => {
    if (!query.trim()) return;
    setError(null);
    setLoading(true);
    setResults(null);
    try {
      const res = await fetch(`/api/orders/track/${encodeURIComponent(query.trim())}`);
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(data.error || 'Aucune commande trouvée.');
      }
      setResults(data);
    } catch (err) {
      setError(err instanceof TypeError ? 'Connexion impossible, réessayez dans un instant.' : err.message);
    } finally {
      setLoading(false);
    }
  };

  // Paiement par carte : vérifier auprès de Konnect, ou relancer un paiement échoué
  const [paying, setPaying] = useState(null);
  const checkPayment = async (orderId) => {
    try {
      await fetch(`/api/orders/${encodeURIComponent(orderId)}/payment/check`, { method: 'POST' });
    } catch {
      /* la recherche affichera l'état connu */
    }
  };
  const retryPayment = async (orderId) => {
    setPaying(orderId);
    setError(null);
    try {
      const res = await fetch(`/api/orders/${encodeURIComponent(orderId)}/payment/retry`, { method: 'POST' });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || !data.payUrl) throw new Error(data.error || 'Le paiement par carte est momentanément indisponible.');
      window.location.assign(data.payUrl);
    } catch (err) {
      setError(err instanceof TypeError ? 'Connexion impossible, réessayez dans un instant.' : err.message);
      setPaying(null);
    }
  };

  // Recherche automatique juste après une commande (et au retour de la page de paiement)
  useEffect(() => {
    const fromPayment = new URLSearchParams(window.location.search).get('paiement') === 'retour';
    if (initialQuery && fromPayment) {
      checkPayment(initialQuery).then(() => runSearch(initialQuery));
      window.history.replaceState(null, '', window.location.pathname);
    } else if (initialQuery) runSearch(initialQuery);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialQuery]);

  const handleSearch = (e) => {
    e.preventDefault();
    runSearch(searchQuery);
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
                    {order.deliveryMethod === 'pickup' && (
                      <span className="text-xs font-semibold text-blue-700">
                        Retrait au local{order.discount > 0 ? ` · remise -${order.discount.toFixed(2)} DT` : ''}
                      </span>
                    )}
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

                {order.deliveryMethod === 'pickup' && (
                  <div className="flex items-start gap-2 p-3 rounded-xl bg-blue-50 text-sm text-blue-950">
                    <Store className="w-4 h-4 text-blue-600 shrink-0 mt-0.5" />
                    <span>
                      Retrait au local : <strong>{pickupInfo.address}</strong>, {pickupInfo.hours}.{' '}
                      <a href={pickupInfo.mapUrl} target="_blank" rel="noopener noreferrer" className="underline font-semibold">
                        Voir sur la carte
                      </a>
                    </span>
                  </div>
                )}

                {order.paymentMethod === 'card' && (
                  <div className={`flex flex-wrap items-center justify-between gap-3 p-3 rounded-xl text-sm ${
                    order.paymentStatus === 'paid' ? 'bg-blue-50 text-blue-900' : 'bg-amber-50 text-amber-900'
                  }`}>
                    <span className="flex items-center gap-2 font-semibold">
                      <CreditCard className="w-4 h-4 shrink-0" />
                      {order.paymentStatus === 'paid'
                        ? 'Payée par carte bancaire. Rien à payer à la réception.'
                        : order.paymentStatus === 'failed'
                          ? "Le paiement par carte n'a pas abouti."
                          : 'Paiement par carte en attente.'}
                    </span>
                    {order.paymentStatus !== 'paid' && order.status !== 'cancelled' && (
                      <button
                        onClick={() => retryPayment(order.id)}
                        disabled={paying === order.id}
                        className="inline-flex items-center gap-1.5 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white font-bold text-xs rounded-lg disabled:opacity-60"
                      >
                        {paying === order.id ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <CreditCard className="w-3.5 h-3.5" />}
                        Payer {order.total.toFixed(2)} DT par carte
                      </button>
                    )}
                  </div>
                )}

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
