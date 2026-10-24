import React, { useMemo, useState } from 'react';
import { Wallet, ShoppingBag, Banknote, Receipt, Building2, Boxes, ChevronRight, Inbox } from 'lucide-react';
import { Card, Kpi, OrderBadge, ORDER_STATUS, TONE_BAR, dt, dateTime, EmptyState } from './ui';

function RevenueChart({ daily }) {
  const [hover, setHover] = useState(null);
  const max = Math.max(...daily.map((d) => d.revenue), 1);
  const total = daily.reduce((s, d) => s + d.revenue, 0);
  const orders = daily.reduce((s, d) => s + d.orders, 0);
  const shown = hover !== null ? daily[hover] : null;

  return (
    <div>
      <div className="flex items-baseline justify-between mb-4">
        <div>
          <div className="text-2xl font-black text-slate-900 tabular-nums">{dt(shown ? shown.revenue : total)}</div>
          <div className="text-xs text-slate-500">
            {shown
              ? `${new Date(shown.day).toLocaleDateString('fr-FR', { weekday: 'long', day: 'numeric', month: 'long' })} · ${shown.orders} commande(s)`
              : `${orders} commande(s) sur les 30 derniers jours`}
          </div>
        </div>
      </div>
      <div className="flex items-end gap-[3px] h-40" onMouseLeave={() => setHover(null)}>
        {daily.map((d, i) => (
          <div
            key={d.day}
            onMouseEnter={() => setHover(i)}
            className="flex-1 h-full flex items-end cursor-default"
            title={`${d.day} : ${dt(d.revenue)}`}
          >
            <div
              className={`w-full rounded-t-[3px] transition-colors ${hover === i ? 'bg-blue-700' : d.revenue ? 'bg-blue-500' : 'bg-slate-100'}`}
              style={{ height: `${d.revenue ? Math.max(4, (d.revenue / max) * 100) : 3}%` }}
            />
          </div>
        ))}
      </div>
      <div className="flex justify-between text-[10px] text-slate-400 mt-1.5">
        <span>{new Date(daily[0]?.day).toLocaleDateString('fr-FR', { day: 'numeric', month: 'short' })}</span>
        <span>Aujourd'hui</span>
      </div>
    </div>
  );
}

function StatusBreakdown({ byStatus }) {
  const total = byStatus.reduce((s, r) => s + r.count, 0) || 1;
  const ordered = Object.keys(ORDER_STATUS).map((k) => byStatus.find((r) => r.status === k) || { status: k, count: 0, total: 0 });
  return (
    <div className="space-y-4">
      <div className="flex h-3 rounded-full overflow-hidden bg-slate-100">
        {ordered.map((r) =>
          r.count ? (
            <div key={r.status} className={TONE_BAR[ORDER_STATUS[r.status].tone]} style={{ width: `${(r.count / total) * 100}%` }} />
          ) : null
        )}
      </div>
      <div className="space-y-2">
        {ordered.map((r) => (
          <div key={r.status} className="flex items-center justify-between text-sm">
            <span className="flex items-center gap-2 text-slate-600">
              <span className={`w-2.5 h-2.5 rounded-full ${TONE_BAR[ORDER_STATUS[r.status].tone]}`} />
              {ORDER_STATUS[r.status].label}
            </span>
            <span className="tabular-nums text-slate-900 font-semibold">
              {r.count} <span className="text-slate-400 font-normal">· {dt(r.total)}</span>
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function RankList({ rows, valueKey, labelKey, format, sub }) {
  const max = Math.max(...rows.map((r) => r[valueKey]), 1);
  if (!rows.length) return <EmptyState title="Pas encore de ventes" />;
  return (
    <div className="space-y-3">
      {rows.map((r) => (
        <div key={r[labelKey]}>
          <div className="flex justify-between gap-3 text-sm">
            <span className="text-slate-700 truncate">{r[labelKey]}</span>
            <span className="font-semibold tabular-nums shrink-0">{format(r[valueKey])}</span>
          </div>
          <div className="flex items-center gap-2 mt-1">
            <div className="flex-1 h-1.5 rounded-full bg-slate-100 overflow-hidden">
              <div className="h-full bg-blue-500 rounded-full" style={{ width: `${(r[valueKey] / max) * 100}%` }} />
            </div>
            <span className="text-[11px] text-slate-400 w-20 text-right">{sub(r)}</span>
          </div>
        </div>
      ))}
    </div>
  );
}

export function Overview({ stats, orders, leads, products, goTo, openOrder }) {
  const toProcess = useMemo(
    () => orders.filter((o) => ['pending', 'confirmed', 'shipped'].includes(o.status)).slice(0, 6),
    [orders]
  );
  const lowStock = products.filter((p) => p.stock <= 10);

  if (!stats) {
    return <EmptyState icon={Inbox} title="Statistiques indisponibles">Vérifiez que le serveur et la base MySQL sont démarrés, puis actualisez.</EmptyState>;
  }

  const trend = stats.prevMonthRevenue > 0 ? ((stats.monthRevenue - stats.prevMonthRevenue) / stats.prevMonthRevenue) * 100 : null;

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 xl:grid-cols-4 gap-3 sm:gap-4">
        <Kpi icon={Wallet} label="Chiffre d'affaires du mois" value={dt(stats.monthRevenue)} trend={trend} sub={trend === null ? `${stats.monthOrders} commande(s) ce mois-ci` : 'vs mois dernier'} />
        <Kpi
          icon={ShoppingBag}
          label="Commandes à confirmer"
          value={stats.pendingOrders}
          sub="à appeler"
          highlight={stats.pendingOrders > 0}
          onClick={() => goTo('orders', 'pending')}
        />
        <Kpi icon={Banknote} label="À encaisser (livraison)" value={dt(stats.toCollect)} sub={`${stats.toCollectCount} commande(s) en cours`} onClick={() => goTo('orders', 'open')} />
        <Kpi icon={Receipt} label="Panier moyen" value={dt(stats.avgBasket, 1)} sub={`${stats.validOrders} commandes valides`} />
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-5">
        <Card title="Ventes des 30 derniers jours" className="xl:col-span-2">
          <RevenueChart daily={stats.daily} />
        </Card>
        <Card title="Commandes par statut">
          <StatusBreakdown byStatus={stats.byStatus} />
        </Card>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-5">
        <Card
          title="À traiter"
          className="xl:col-span-2"
          bodyClass=""
          action={
            <button onClick={() => goTo('orders', 'open')} className="text-xs text-blue-600 hover:underline font-semibold flex items-center gap-0.5">
              Toutes les commandes <ChevronRight className="w-3.5 h-3.5" />
            </button>
          }
        >
          {toProcess.length ? (
            <div className="divide-y divide-slate-100">
              {toProcess.map((o) => (
                <button
                  key={o.id}
                  onClick={() => openOrder(o.id)}
                  className="w-full px-5 py-3 flex items-center gap-4 hover:bg-slate-50 text-left transition"
                >
                  <span className="font-mono text-xs font-bold text-blue-700 w-20 shrink-0">{o.id}</span>
                  <span className="flex-1 min-w-0">
                    <span className="block text-sm font-semibold text-slate-900 truncate">{o.customer?.fullName}</span>
                    <span className="block text-xs text-slate-400">
                      {o.customer?.governorate} · {dateTime(o.date)}
                    </span>
                  </span>
                  <span className="text-sm font-bold tabular-nums hidden sm:block">{dt(o.total, 2)}</span>
                  <OrderBadge status={o.status} />
                </button>
              ))}
            </div>
          ) : (
            <EmptyState icon={Inbox} title="Tout est à jour">Aucune commande en attente.</EmptyState>
          )}
        </Card>

        <div className="space-y-5">
          <Card title="Alertes">
            <div className="space-y-2.5 text-sm">
              <button onClick={() => goTo('leads', 'new')} className="w-full flex items-center justify-between hover:text-blue-700">
                <span className="flex items-center gap-2 text-slate-600">
                  <Building2 className="w-4 h-4 text-blue-500" /> Nouvelles demandes pro
                </span>
                <span className="font-bold">{stats.newLeads}</span>
              </button>
              <button onClick={() => goTo('products', 'low')} className="w-full flex items-center justify-between hover:text-blue-700">
                <span className="flex items-center gap-2 text-slate-600">
                  <Boxes className="w-4 h-4 text-amber-500" /> Produits en stock faible
                </span>
                <span className={`font-bold ${lowStock.length ? 'text-amber-600' : ''}`}>{lowStock.length}</span>
              </button>
              {lowStock.slice(0, 3).map((p) => (
                <div key={p.id} className="flex justify-between text-xs text-slate-500 pl-6">
                  <span className="truncate">{p.name}</span>
                  <span className="font-semibold text-amber-600 shrink-0">{p.stock} u.</span>
                </div>
              ))}
              <div className="flex items-center justify-between text-slate-600 pt-2 border-t border-slate-100">
                <span>Demandes pro au total</span>
                <span className="font-bold text-slate-900">{leads.length}</span>
              </div>
            </div>
          </Card>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <Card title="Meilleurs produits (chiffre d'affaires)">
          <RankList rows={stats.topProducts} valueKey="revenue" labelKey="name" format={(v) => dt(v)} sub={(r) => `${r.quantity} vendus`} />
        </Card>
        <Card title="Ventes par gouvernorat">
          <RankList rows={stats.byGovernorate} valueKey="revenue" labelKey="governorate" format={(v) => dt(v)} sub={(r) => `${r.orders} cmd`} />
        </Card>
      </div>
    </div>
  );
}
