import React, { useEffect } from 'react';
import { CheckCircle, Clock, Truck, PackageCheck, XCircle, CheckCircle2, AlertCircle, X } from 'lucide-react';

export const ORDER_STATUS = {
  pending: { label: 'À confirmer', short: 'À confirmer', tone: 'amber', icon: Clock },
  confirmed: { label: 'Confirmée', short: 'Confirmée', tone: 'blue', icon: CheckCircle },
  shipped: { label: 'En livraison', short: 'Expédiée', tone: 'indigo', icon: Truck },
  delivered: { label: 'Livrée et payée', short: 'Livrée', tone: 'green', icon: PackageCheck },
  cancelled: { label: 'Annulée', short: 'Annulée', tone: 'slate', icon: XCircle },
};

// Étape suivante proposée pour chaque statut (flux paiement à la livraison)
export const NEXT_ACTION = {
  pending: { status: 'confirmed', label: 'Confirmer' },
  confirmed: { status: 'shipped', label: 'Expédier' },
  shipped: { status: 'delivered', label: 'Livrée et encaissée' },
};

export const LEAD_STATUS = {
  new: { label: 'Nouveau', tone: 'blue' },
  contacted: { label: 'Contacté', tone: 'indigo' },
  in_progress: { label: 'En cours', tone: 'amber' },
  qualified: { label: 'Devis envoyé', tone: 'sky' },
  converted: { label: 'Gagné', tone: 'green' },
  lost: { label: 'Perdu', tone: 'slate' },
};

const TONES = {
  amber: 'bg-amber-50 text-amber-800 ring-amber-200',
  blue: 'bg-blue-50 text-blue-800 ring-blue-200',
  indigo: 'bg-indigo-50 text-indigo-800 ring-indigo-200',
  green: 'bg-emerald-50 text-emerald-800 ring-emerald-200',
  sky: 'bg-sky-50 text-sky-800 ring-sky-200',
  slate: 'bg-slate-100 text-slate-600 ring-slate-200',
  red: 'bg-red-50 text-red-700 ring-red-200',
};

export const TONE_BAR = {
  amber: 'bg-amber-400',
  blue: 'bg-blue-500',
  indigo: 'bg-indigo-500',
  green: 'bg-emerald-500',
  sky: 'bg-sky-400',
  slate: 'bg-slate-300',
};

export const dt = (n, digits = 0) =>
  `${(Number(n) || 0).toLocaleString('fr-FR', { minimumFractionDigits: digits, maximumFractionDigits: digits })} DT`;

export const shortDate = (d) =>
  new Date(d).toLocaleDateString('fr-FR', { day: '2-digit', month: 'short', year: 'numeric' });

export const dateTime = (d) =>
  new Date(d).toLocaleString('fr-FR', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' });

export function Badge({ tone = 'slate', icon: Icon, children }) {
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-bold ring-1 ring-inset whitespace-nowrap ${TONES[tone]}`}>
      {Icon && <Icon className="w-3 h-3" />}
      {children}
    </span>
  );
}

export function OrderBadge({ status }) {
  const cfg = ORDER_STATUS[status] || ORDER_STATUS.pending;
  return <Badge tone={cfg.tone} icon={cfg.icon}>{cfg.short}</Badge>;
}

export function LeadBadge({ status }) {
  const cfg = LEAD_STATUS[status] || LEAD_STATUS.new;
  return <Badge tone={cfg.tone}>{cfg.label}</Badge>;
}

export function Card({ title, action, children, className = '', bodyClass = 'p-5' }) {
  return (
    <section className={`bg-white rounded-2xl border border-slate-200 shadow-sm ${className}`}>
      {(title || action) && (
        <div className="px-5 py-3.5 border-b border-slate-100 flex items-center justify-between gap-3">
          <h2 className="text-sm font-bold text-slate-900">{title}</h2>
          {action}
        </div>
      )}
      <div className={bodyClass}>{children}</div>
    </section>
  );
}

export function Kpi({ icon: Icon, label, value, sub, trend, onClick, highlight }) {
  const Tag = onClick ? 'button' : 'div';
  return (
    <Tag
      onClick={onClick}
      className={`text-left rounded-2xl border p-4 sm:p-5 bg-white shadow-sm transition ${
        highlight ? 'border-amber-300 ring-1 ring-amber-200' : 'border-slate-200'
      } ${onClick ? 'hover:border-blue-300 hover:shadow-md' : ''}`}
    >
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold text-slate-500">{label}</span>
        {Icon && <Icon className="w-4 h-4 text-slate-400" />}
      </div>
      <div className="text-2xl font-black text-slate-900 mt-1.5 tabular-nums">{value}</div>
      <div className="flex items-center gap-2 mt-1 text-[11px]">
        {trend !== undefined && trend !== null && Number.isFinite(trend) && (
          <span className={`font-bold ${trend >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>
            {trend >= 0 ? '▲' : '▼'} {Math.abs(Math.round(trend))} %
          </span>
        )}
        {sub && <span className="text-slate-500">{sub}</span>}
      </div>
    </Tag>
  );
}

export function EmptyState({ icon: Icon, title, children }) {
  return (
    <div className="py-12 text-center">
      {Icon && <Icon className="w-8 h-8 text-slate-300 mx-auto mb-2" />}
      <div className="text-sm font-semibold text-slate-600">{title}</div>
      {children && <div className="text-xs text-slate-400 mt-1">{children}</div>}
    </div>
  );
}

export function Toast({ toast, onClose }) {
  useEffect(() => {
    if (!toast) return undefined;
    const t = setTimeout(onClose, 3500);
    return () => clearTimeout(t);
  }, [toast, onClose]);

  if (!toast) return null;
  const isError = toast.type === 'error';
  return (
    <div className="fixed top-4 left-1/2 -translate-x-1/2 z-[60] animate-in slide-in-from-top-4 fade-in duration-200">
      <div
        role="status"
        className={`flex items-center gap-2.5 pl-4 pr-2 py-2.5 rounded-xl shadow-xl text-sm font-semibold ${
          isError ? 'bg-red-600 text-white' : 'bg-slate-900 text-white'
        }`}
      >
        {isError ? <AlertCircle className="w-4 h-4" /> : <CheckCircle2 className="w-4 h-4 text-emerald-400" />}
        {toast.message}
        <button onClick={onClose} className="p-1 rounded-lg hover:bg-white/10" aria-label="Fermer">
          <X className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  );
}

export function SearchInput({ value, onChange, placeholder, icon: Icon }) {
  return (
    <div className="relative flex-1 min-w-[200px] max-w-md">
      {Icon && <Icon className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />}
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="pl-9 pr-3 py-2 border border-slate-200 rounded-xl text-sm w-full bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
      />
    </div>
  );
}

export function FilterChips({ options, value, onChange }) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {options.map((o) => (
        <button
          key={o.value}
          onClick={() => onChange(o.value)}
          className={`px-3 py-1.5 rounded-lg text-xs font-bold border transition ${
            value === o.value ? 'bg-slate-900 border-slate-900 text-white' : 'bg-white border-slate-200 text-slate-600 hover:border-slate-300'
          }`}
        >
          {o.label}
          {o.count !== undefined && <span className={`ml-1.5 ${value === o.value ? 'text-slate-300' : 'text-slate-400'}`}>{o.count}</span>}
        </button>
      ))}
    </div>
  );
}

export function downloadCsv(filename, rows) {
  const escape = (v) => `"${String(v ?? '').replace(/"/g, '""')}"`;
  const csv = rows.map((r) => r.map(escape).join(';')).join('\r\n');
  const blob = new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export const telLink = (phone) => `tel:+216${String(phone || '').replace(/[^0-9]/g, '').replace(/^216/, '')}`;
export const waLink = (phone, text = '') =>
  `https://wa.me/216${String(phone || '').replace(/[^0-9]/g, '').replace(/^216/, '')}${text ? `?text=${encodeURIComponent(text)}` : ''}`;
