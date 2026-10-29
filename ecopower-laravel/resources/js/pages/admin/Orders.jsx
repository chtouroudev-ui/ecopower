import React, { useEffect, useMemo, useState } from 'react';
import { Search, Download, X, Phone, MessageCircle, MapPin, Award, Printer, Inbox, ChevronRight, Save, XCircle, RotateCcw, Store, CreditCard } from 'lucide-react';
import {
  ORDER_STATUS,
  NEXT_ACTION,
  OrderBadge,
  FilterChips,
  SearchInput,
  EmptyState,
  dt,
  dateTime,
  shortDate,
  downloadCsv,
  telLink,
  waLink,
} from './ui';

const STEPS = ['pending', 'confirmed', 'shipped', 'delivered'];

const paymentLabel = (o) =>
  o.paymentMethod !== 'card'
    ? o.deliveryMethod === 'pickup' ? 'espèces au retrait' : 'espèces à la livraison'
    : o.paymentStatus === 'paid' ? 'payée par carte (Konnect)'
      : o.paymentStatus === 'failed' ? 'carte : paiement échoué' : 'carte : paiement en attente';

function OrderDrawer({ order, onClose, onStatus, onNotes, onCertificate, onPrint }) {
  const [notes, setNotes] = useState(order.notes || '');
  const [saving, setSaving] = useState(false);
  useEffect(() => setNotes(order.notes || ''), [order.id, order.notes]);
  useEffect(() => {
    const onKey = (e) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  const next = NEXT_ACTION[order.status];
  const stepIndex = STEPS.indexOf(order.status);
  const run = async (fn) => {
    setSaving(true);
    try {
      await fn();
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50">
      <div className="absolute inset-0 bg-slate-900/40 animate-in fade-in duration-150" onClick={onClose} />
      <aside className="absolute inset-y-0 right-0 w-full max-w-lg bg-white shadow-2xl flex flex-col animate-in slide-in-from-right duration-200">
        <div className="px-5 py-4 border-b border-slate-200 flex items-start justify-between gap-3">
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-lg font-black text-slate-900 font-mono">{order.id}</h2>
              <OrderBadge status={order.status} />
            </div>
            <p className="text-xs text-slate-500 mt-0.5">
              Passée le {dateTime(order.date)} · {order.deliveryMethod === 'pickup' ? 'retrait au local' : 'livraison'} · {paymentLabel(order)}
            </p>
          </div>
          <button onClick={onClose} className="p-2 rounded-xl hover:bg-slate-100" aria-label="Fermer">
            <X className="w-5 h-5 text-slate-500" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-5 space-y-5">
          {order.status !== 'cancelled' && (
            <ol className="grid grid-cols-4 gap-1">
              {STEPS.map((s, i) => (
                <li key={s} className="text-center">
                  <div className={`h-1.5 rounded-full ${i <= stepIndex ? 'bg-blue-600' : 'bg-slate-200'}`} />
                  <div className={`text-[11px] mt-1.5 font-semibold ${i <= stepIndex ? 'text-slate-900' : 'text-slate-400'}`}>
                    {ORDER_STATUS[s].short}
                  </div>
                </li>
              ))}
            </ol>
          )}

          <section className="rounded-xl border border-slate-200 p-4 space-y-3">
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="font-bold text-slate-900">{order.customer?.fullName}</div>
                <div className="text-sm text-slate-600 font-mono">{order.customer?.phone}</div>
                {order.customer?.email && <div className="text-xs text-slate-500">{order.customer.email}</div>}
              </div>
              <div className="flex gap-1.5">
                <a href={telLink(order.customer?.phone)} className="p-2 rounded-lg border border-slate-200 hover:bg-blue-50 hover:border-blue-200" title="Appeler">
                  <Phone className="w-4 h-4 text-blue-600" />
                </a>
                <a
                  href={waLink(order.customer?.phone, `Bonjour ${order.customer?.fullName || ''}, EcoPower vous contacte pour votre commande ${order.id}.`)}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="p-2 rounded-lg border border-slate-200 hover:bg-emerald-50 hover:border-emerald-200"
                  title="WhatsApp"
                >
                  <MessageCircle className="w-4 h-4 text-emerald-600" />
                </a>
              </div>
            </div>
            {order.deliveryMethod === 'pickup' ? (
              <div className="flex items-start gap-2 text-sm font-semibold text-blue-800 bg-blue-50 rounded-lg px-3 py-2">
                <Store className="w-4 h-4 mt-0.5 shrink-0" />
                <span>Retrait au local : pas de livraison, le client vient chercher sa commande ({order.customer?.governorate}).</span>
              </div>
            ) : (
              <div className="flex items-start gap-2 text-sm text-slate-600">
                <MapPin className="w-4 h-4 text-slate-400 mt-0.5 shrink-0" />
                <span>
                  {order.customer?.address}
                  <br />
                  {[...new Set([order.customer?.city, order.customer?.governorate].filter(Boolean))].join(', ')}
                </span>
              </div>
            )}
          </section>

          <section className="rounded-xl border border-slate-200 overflow-hidden">
            <table className="w-full text-sm">
              <tbody className="divide-y divide-slate-100">
                {order.items?.map((it) => (
                  <tr key={it.id || it.name}>
                    <td className="px-4 py-2.5">
                      <div className="font-medium text-slate-800">{it.name}</div>
                      {it.serials?.length > 0 && <div className="text-[10px] font-mono text-slate-400 truncate max-w-[260px]">{it.serials.join(' · ')}</div>}
                    </td>
                    <td className="px-2 py-2.5 text-slate-500 text-right whitespace-nowrap">× {it.quantity}</td>
                    <td className="px-4 py-2.5 text-right tabular-nums whitespace-nowrap">{dt(it.price * it.quantity, 2)}</td>
                  </tr>
                ))}
              </tbody>
              <tfoot className="bg-slate-50 text-sm">
                {order.discount > 0 && (
                  <tr>
                    <td colSpan={2} className="px-4 py-1.5 text-blue-700">Remise retrait au local (-10%)</td>
                    <td className="px-4 py-1.5 text-right tabular-nums text-blue-700">-{dt(order.discount, 2)}</td>
                  </tr>
                )}
                <tr>
                  <td colSpan={2} className="px-4 py-1.5 text-slate-500">Livraison</td>
                  <td className="px-4 py-1.5 text-right tabular-nums">
                    {order.deliveryMethod === 'pickup' ? 'Retrait au local' : order.deliveryFee ? dt(order.deliveryFee, 2) : 'Offerte'}
                  </td>
                </tr>
                <tr className="font-black text-slate-900">
                  <td colSpan={2} className="px-4 py-2">{order.paymentStatus === 'paid' ? 'Déjà payé par carte' : 'À encaisser'}</td>
                  <td className="px-4 py-2 text-right tabular-nums">{order.paymentStatus === 'paid' ? dt(0, 2) : dt(order.total, 2)}</td>
                </tr>
              </tfoot>
            </table>
          </section>

          <section>
            <label className="text-xs font-bold text-slate-600 block mb-1.5">Note interne</label>
            <textarea
              rows={3}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Ex : client rappelé, livraison prévue jeudi après-midi"
              className="w-full border border-slate-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
            />
            {notes !== (order.notes || '') && (
              <button
                onClick={() => run(() => onNotes(order.id, notes))}
                disabled={saving}
                className="mt-2 inline-flex items-center gap-1.5 px-3 py-1.5 bg-slate-900 text-white text-xs font-bold rounded-lg disabled:opacity-60"
              >
                <Save className="w-3.5 h-3.5" /> Enregistrer la note
              </button>
            )}
          </section>

          <section className="flex flex-wrap gap-2">
            <button onClick={() => onCertificate(order.id)} className="inline-flex items-center gap-1.5 px-3 py-2 border border-slate-200 rounded-lg text-xs font-bold text-slate-700 hover:bg-slate-50">
              <Award className="w-3.5 h-3.5 text-blue-600" /> Certificat
            </button>
            <button onClick={() => onPrint(order.id)} className="inline-flex items-center gap-1.5 px-3 py-2 border border-slate-200 rounded-lg text-xs font-bold text-slate-700 hover:bg-slate-50">
              <Printer className="w-3.5 h-3.5 text-blue-600" /> Imprimer
            </button>
          </section>
        </div>

        <div className="p-4 border-t border-slate-200 flex gap-2 bg-slate-50">
          {order.status === 'cancelled' ? (
            <button
              disabled={saving}
              onClick={() => run(() => onStatus(order.id, 'pending'))}
              className="flex-1 inline-flex items-center justify-center gap-2 py-2.5 rounded-xl border border-slate-300 bg-white text-sm font-bold text-slate-700 disabled:opacity-60"
            >
              <RotateCcw className="w-4 h-4" /> Réactiver la commande
            </button>
          ) : (
            <>
              {order.status !== 'delivered' && (
                <button
                  disabled={saving}
                  onClick={() => {
                    if (window.confirm(`Annuler la commande ${order.id} ? Le stock sera remis à jour.`)) run(() => onStatus(order.id, 'cancelled'));
                  }}
                  className="inline-flex items-center gap-1.5 px-4 py-2.5 rounded-xl border border-slate-300 bg-white text-sm font-bold text-red-600 hover:bg-red-50 disabled:opacity-60"
                >
                  <XCircle className="w-4 h-4" /> Annuler
                </button>
              )}
              {next && (
                <button
                  disabled={saving}
                  onClick={() => run(() => onStatus(order.id, next.status))}
                  className="flex-1 inline-flex items-center justify-center gap-2 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-sm font-bold disabled:opacity-60"
                >
                  {next.label} <ChevronRight className="w-4 h-4" />
                </button>
              )}
              {order.status === 'delivered' && (
                <div className="flex-1 text-center text-sm font-semibold text-emerald-700 py-2.5">Commande livrée et encaissée</div>
              )}
            </>
          )}
        </div>
      </aside>
    </div>
  );
}

export function Orders({ orders, filter, setFilter, openId, setOpenId, onStatus, onNotes, onCertificate, onPrint }) {
  const [query, setQuery] = useState('');

  const counts = useMemo(() => {
    const c = { all: orders.length, open: 0 };
    orders.forEach((o) => {
      c[o.status] = (c[o.status] || 0) + 1;
      if (['pending', 'confirmed', 'shipped'].includes(o.status)) c.open += 1;
    });
    return c;
  }, [orders]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return orders.filter((o) => {
      if (filter === 'open' && !['pending', 'confirmed', 'shipped'].includes(o.status)) return false;
      if (filter !== 'all' && filter !== 'open' && o.status !== filter) return false;
      if (!q) return true;
      return (
        o.id.toLowerCase().includes(q) ||
        o.customer?.fullName?.toLowerCase().includes(q) ||
        o.customer?.phone?.includes(q) ||
        o.customer?.governorate?.toLowerCase().includes(q)
      );
    });
  }, [orders, filter, query]);

  const exportCsv = () => {
    downloadCsv(`commandes-ecopower-${new Date().toISOString().slice(0, 10)}.csv`, [
      ['Référence', 'Date', 'Client', 'Téléphone', 'Gouvernorat', 'Ville', 'Adresse', 'Articles', 'Mode', 'Paiement', 'Remise', 'Livraison', 'Total', 'Statut', 'Note'],
      ...filtered.map((o) => [
        o.id,
        shortDate(o.date),
        o.customer?.fullName,
        o.customer?.phone,
        o.customer?.governorate,
        o.customer?.city,
        o.customer?.address,
        o.items?.map((i) => `${i.quantity}x ${i.name}`).join(' | '),
        o.deliveryMethod === 'pickup' ? 'Retrait au local' : 'Livraison',
        paymentLabel(o),
        o.discount || 0,
        o.deliveryFee,
        o.total,
        ORDER_STATUS[o.status]?.label || o.status,
        o.notes,
      ]),
    ]);
  };

  const opened = orders.find((o) => o.id === openId);

  return (
    <div className="space-y-4">
      <div className="flex flex-col lg:flex-row lg:items-center gap-3 justify-between">
        <FilterChips
          value={filter}
          onChange={setFilter}
          options={[
            { value: 'open', label: 'En cours', count: counts.open },
            { value: 'pending', label: 'À confirmer', count: counts.pending || 0 },
            { value: 'confirmed', label: 'Confirmées', count: counts.confirmed || 0 },
            { value: 'shipped', label: 'En livraison', count: counts.shipped || 0 },
            { value: 'delivered', label: 'Livrées', count: counts.delivered || 0 },
            { value: 'cancelled', label: 'Annulées', count: counts.cancelled || 0 },
            { value: 'all', label: 'Toutes', count: counts.all },
          ]}
        />
        <div className="flex gap-2">
          <SearchInput value={query} onChange={setQuery} placeholder="Réf., nom, téléphone, gouvernorat" icon={Search} />
          <button onClick={exportCsv} className="inline-flex items-center gap-1.5 px-3 py-2 border border-slate-200 bg-white rounded-xl text-xs font-bold text-slate-700 hover:bg-slate-50 whitespace-nowrap">
            <Download className="w-4 h-4" /> Export CSV
          </button>
        </div>
      </div>

      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
        {filtered.length === 0 ? (
          <EmptyState icon={Inbox} title="Aucune commande">Modifiez le filtre ou la recherche.</EmptyState>
        ) : (
          <>
            {/* Mobile */}
            <div className="md:hidden divide-y divide-slate-100">
              {filtered.map((o) => (
                <button key={o.id} onClick={() => setOpenId(o.id)} className="w-full p-4 text-left flex items-center gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs font-bold text-blue-700">{o.id}</span>
                      <OrderBadge status={o.status} />
                    </div>
                    <div className="text-sm font-semibold text-slate-900 truncate mt-1">{o.customer?.fullName}</div>
                    <div className="text-xs text-slate-400">{o.customer?.governorate} · {shortDate(o.date)}</div>
                  </div>
                  <div className="text-sm font-bold tabular-nums">{dt(o.total, 2)}</div>
                </button>
              ))}
            </div>
            {/* Desktop */}
            <table className="hidden md:table w-full text-sm">
              <thead>
                <tr className="bg-slate-50 text-[11px] uppercase font-bold text-slate-500 border-b border-slate-200">
                  <th className="px-4 py-3 text-left">Réf.</th>
                  <th className="px-4 py-3 text-left">Client</th>
                  <th className="px-4 py-3 text-left">Livraison</th>
                  <th className="px-4 py-3 text-left">Date</th>
                  <th className="px-4 py-3 text-right">Total</th>
                  <th className="px-4 py-3 text-left">Statut</th>
                  <th className="px-4 py-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {filtered.map((o) => {
                  const next = NEXT_ACTION[o.status];
                  return (
                    <tr key={o.id} onClick={() => setOpenId(o.id)} className="hover:bg-slate-50 cursor-pointer">
                      <td className="px-4 py-3 font-mono text-xs font-bold text-blue-700">{o.id}</td>
                      <td className="px-4 py-3">
                        <div className="font-semibold text-slate-900">{o.customer?.fullName}</div>
                        <div className="text-xs text-slate-400 font-mono">{o.customer?.phone}</div>
                      </td>
                      <td className="px-4 py-3 text-xs text-slate-600">
                        {o.deliveryMethod === 'pickup' ? (
                          <span className="inline-flex items-center gap-1 font-semibold text-blue-700"><Store className="w-3.5 h-3.5" /> Retrait au local</span>
                        ) : (
                          [...new Set([o.customer?.city, o.customer?.governorate].filter(Boolean))].join(', ')
                        )}
                      </td>
                      <td className="px-4 py-3 text-xs text-slate-500 whitespace-nowrap">{dateTime(o.date)}</td>
                      <td className="px-4 py-3 text-right font-bold tabular-nums whitespace-nowrap">
                        {dt(o.total, 2)}
                        {o.paymentMethod === 'card' && (
                          <span
                            title={paymentLabel(o)}
                            className={`ms-1.5 inline-flex align-middle ${o.paymentStatus === 'paid' ? 'text-blue-600' : 'text-amber-500'}`}
                          >
                            <CreditCard className="w-3.5 h-3.5" />
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3"><OrderBadge status={o.status} /></td>
                      <td className="px-4 py-3 text-right" onClick={(e) => e.stopPropagation()}>
                        {next ? (
                          <button
                            onClick={() => onStatus(o.id, next.status)}
                            className="px-3 py-1.5 rounded-lg bg-blue-50 text-blue-700 hover:bg-blue-100 text-xs font-bold whitespace-nowrap"
                          >
                            {next.label}
                          </button>
                        ) : (
                          <ChevronRight className="w-4 h-4 text-slate-300 inline" />
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </>
        )}
      </div>

      {opened && (
        <OrderDrawer
          order={opened}
          onClose={() => setOpenId(null)}
          onStatus={onStatus}
          onNotes={onNotes}
          onCertificate={onCertificate}
          onPrint={onPrint}
        />
      )}
    </div>
  );
}
