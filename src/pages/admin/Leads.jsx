import React, { useMemo, useState } from 'react';
import { Search, Phone, Mail, MessageCircle, Building2, Save, Download } from 'lucide-react';
import { LEAD_STATUS, LeadBadge, FilterChips, SearchInput, EmptyState, shortDate, telLink, waLink, downloadCsv } from './ui';

function LeadCard({ lead, onUpdate }) {
  const [notes, setNotes] = useState(lead.notes || '');
  const dirty = notes !== (lead.notes || '');
  return (
    <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-4 sm:p-5 space-y-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className="font-bold text-slate-900">{lead.company}</h3>
            <LeadBadge status={lead.status} />
          </div>
          <div className="text-xs text-slate-500 mt-0.5">
            {lead.id} · reçu le {shortDate(lead.date)} · <span className="capitalize">{lead.type}</span>
            {lead.roomsCount ? ` · ${lead.roomsCount} chambres` : ''}
          </div>
        </div>
        <select
          value={lead.status}
          onChange={(e) => onUpdate(lead.id, { status: e.target.value })}
          className="text-xs border border-slate-200 rounded-lg px-2 py-1.5 font-semibold focus:outline-none focus:ring-2 focus:ring-blue-500 shrink-0"
          aria-label="Statut"
        >
          {Object.entries(LEAD_STATUS).map(([v, c]) => <option key={v} value={v}>{c.label}</option>)}
        </select>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-sm">
        <div>
          <div className="text-[11px] font-semibold text-slate-400 uppercase">Contact</div>
          <div className="text-slate-800 font-medium">{lead.contactPerson || '—'}</div>
          {lead.role && <div className="text-xs text-slate-500">{lead.role}</div>}
        </div>
        <div>
          <div className="text-[11px] font-semibold text-slate-400 uppercase">Facture eau / mois</div>
          <div className="text-slate-800 font-medium">{lead.currentWaterBillMonthly || '—'}</div>
        </div>
        <div>
          <div className="text-[11px] font-semibold text-slate-400 uppercase">Demande</div>
          <div className="text-slate-800">{lead.interest || '—'}</div>
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        {lead.phone && (
          <>
            <a href={telLink(lead.phone)} className="inline-flex items-center gap-1.5 px-3 py-1.5 border border-slate-200 rounded-lg text-xs font-bold text-slate-700 hover:bg-blue-50">
              <Phone className="w-3.5 h-3.5 text-blue-600" /> {lead.phone}
            </a>
            <a href={waLink(lead.phone)} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1.5 px-3 py-1.5 border border-slate-200 rounded-lg text-xs font-bold text-slate-700 hover:bg-emerald-50">
              <MessageCircle className="w-3.5 h-3.5 text-emerald-600" /> WhatsApp
            </a>
          </>
        )}
        {lead.email && (
          <a href={`mailto:${lead.email}`} className="inline-flex items-center gap-1.5 px-3 py-1.5 border border-slate-200 rounded-lg text-xs font-bold text-slate-700 hover:bg-blue-50">
            <Mail className="w-3.5 h-3.5 text-blue-600" /> {lead.email}
          </a>
        )}
      </div>

      <div className="flex gap-2 items-start">
        <textarea
          rows={1}
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder="Note de suivi (rendez-vous, devis envoyé…)"
          className="flex-1 border border-slate-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-y min-h-[38px]"
        />
        {dirty && (
          <button onClick={() => onUpdate(lead.id, { notes })} className="inline-flex items-center gap-1 px-3 py-2 bg-slate-900 text-white rounded-xl text-xs font-bold">
            <Save className="w-3.5 h-3.5" /> OK
          </button>
        )}
      </div>
    </div>
  );
}

export function Leads({ leads, filter, setFilter, onUpdate }) {
  const [query, setQuery] = useState('');
  const counts = useMemo(() => {
    const c = { all: leads.length };
    leads.forEach((l) => (c[l.status] = (c[l.status] || 0) + 1));
    return c;
  }, [leads]);

  const filtered = leads.filter((l) => {
    if (filter !== 'all' && l.status !== filter) return false;
    const q = query.trim().toLowerCase();
    return !q || [l.company, l.contactPerson, l.phone, l.email].some((v) => v?.toLowerCase().includes(q));
  });

  const exportCsv = () =>
    downloadCsv(`demandes-pro-ecopower-${new Date().toISOString().slice(0, 10)}.csv`, [
      ['Référence', 'Date', 'Établissement', 'Type', 'Chambres', 'Contact', 'Fonction', 'Téléphone', 'Email', 'Facture eau', 'Demande', 'Statut', 'Note'],
      ...filtered.map((l) => [
        l.id, shortDate(l.date), l.company, l.type, l.roomsCount, l.contactPerson, l.role, l.phone, l.email,
        l.currentWaterBillMonthly, l.interest, LEAD_STATUS[l.status]?.label || l.status, l.notes,
      ]),
    ]);

  return (
    <div className="space-y-4">
      <div className="flex flex-col lg:flex-row lg:items-center gap-3 justify-between">
        <FilterChips
          value={filter}
          onChange={setFilter}
          options={[
            { value: 'all', label: 'Toutes', count: counts.all },
            ...Object.entries(LEAD_STATUS).map(([v, c]) => ({ value: v, label: c.label, count: counts[v] || 0 })),
          ]}
        />
        <div className="flex gap-2">
          <SearchInput value={query} onChange={setQuery} placeholder="Établissement, contact, téléphone" icon={Search} />
          <button onClick={exportCsv} className="inline-flex items-center gap-1.5 px-3 py-2 border border-slate-200 bg-white rounded-xl text-xs font-bold text-slate-700 hover:bg-slate-50 whitespace-nowrap">
            <Download className="w-4 h-4" /> CSV
          </button>
        </div>
      </div>
      {filtered.length === 0 ? (
        <div className="bg-white rounded-2xl border border-slate-200">
          <EmptyState icon={Building2} title="Aucune demande professionnelle" />
        </div>
      ) : (
        <div className="grid grid-cols-1 2xl:grid-cols-2 gap-4">
          {filtered.map((l) => <LeadCard key={`${l.id}-${l.notes}`} lead={l} onUpdate={onUpdate} />)}
        </div>
      )}
    </div>
  );
}
