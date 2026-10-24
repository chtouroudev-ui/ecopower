import React, { useMemo, useState } from 'react';
import { Search, Eye, Printer, Award } from 'lucide-react';
import { Card, OrderBadge, SearchInput, EmptyState, shortDate } from './ui';

export function Certificates({ orders, onView, onPrint }) {
  const [query, setQuery] = useState('');

  const rows = useMemo(() => {
    const q = query.trim().toLowerCase();
    return orders
      .filter((o) => o.certificateSerial && o.status !== 'cancelled')
      .map((o) => {
        const serials = o.items?.flatMap((i) => i.serials || []) || [];
        const match = q ? serials.find((s) => s.toLowerCase().includes(q)) : null;
        return { order: o, serials, match };
      })
      .filter(({ order, match }) =>
        !q ||
        match ||
        order.id.toLowerCase().includes(q) ||
        order.certificateSerial.toLowerCase().includes(q) ||
        order.customer?.fullName?.toLowerCase().includes(q) ||
        order.customer?.phone?.includes(q)
      );
  }, [orders, query]);

  return (
    <div className="space-y-4">
      <SearchInput value={query} onChange={setQuery} placeholder="N° de série, certificat, commande, client ou téléphone" icon={Search} />
      <Card title={`Certificats de garantie (${rows.length})`} bodyClass="">
        {rows.length === 0 ? (
          <EmptyState icon={Award} title="Aucun certificat trouvé" />
        ) : (
          <div className="divide-y divide-slate-100">
            {rows.map(({ order, serials, match }) => (
              <div key={order.id} className="px-5 py-3 flex flex-col sm:flex-row sm:items-center gap-3">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-mono text-xs font-bold text-blue-700">{order.certificateSerial}</span>
                    <OrderBadge status={order.status} />
                  </div>
                  <div className="text-sm text-slate-800 mt-0.5">
                    {order.customer?.fullName} <span className="text-slate-400">· {order.id} · {shortDate(order.date)} · {serials.length} n° de série</span>
                  </div>
                  {match && <div className="text-[11px] font-mono text-emerald-700 mt-0.5">Série trouvée : {match}</div>}
                </div>
                <div className="flex gap-2 shrink-0">
                  <button onClick={() => onView(order.id)} className="inline-flex items-center gap-1 px-3 py-1.5 border border-slate-200 rounded-lg text-xs font-bold text-slate-700 hover:bg-slate-50">
                    <Eye className="w-3.5 h-3.5 text-blue-600" /> Voir
                  </button>
                  <button onClick={() => onPrint(order.id)} className="inline-flex items-center gap-1 px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-bold">
                    <Printer className="w-3.5 h-3.5" /> Imprimer
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
