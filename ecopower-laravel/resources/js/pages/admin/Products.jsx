import React, { useMemo, useRef, useState } from 'react';
import { Plus, Search, Edit3, Trash2, X, Package, Star, Home, Store, Upload, Loader2, Sparkles } from 'lucide-react';
import { Badge, FilterChips, SearchInput, EmptyState, dt } from './ui';

export const CATEGORIES = {
  packs: 'Packs',
  robinets: 'Robinets',
  douches: 'Douches',
  wc: 'WC',
  accessoires: 'Accessoires',
  energie: 'Énergie',
};

const IMAGES = [
  'pack_appartement_4l.webp', 'pack_appartement_5l.webp', 'pack_maison_4l.webp', 'pack_maison_5l.webp',
  'bague_mousseur_complet.jpg', 'bague_mousseur_grille_bleue.jpg', 'cartouche_hydro_verte.jpg', 'cartouche_hydro_rose_verte.jpg',
  'cartouche_hydro_verte_paire.jpg', 'pomme_douche_chromee.jpg', 'pomme_douche_blanche.jpg', 'ecosac_wc_3l.jpg',
  'bague_inox_male.jpg', 'bague_inox_femelle.jpg', 'ampoule_led_detecteur.jpg',
].map((f) => `/products/${f}`);

const EMPTY = {
  name: '', nameAr: '', category: 'robinets', price: '', oldPrice: '', stock: '50',
  debit: '', warranty: '3 ans', description: '', image: IMAGES[4], isFeatured: false,
  showOnHome: false, pickupDiscount: false, isHero: false,
};

const inputCls = 'w-full border border-slate-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500';

function ProductModal({ initial, onClose, onSave, onUpload }) {
  const [p, setP] = useState(() => ({
    ...EMPTY,
    ...initial,
    price: initial?.price ?? '',
    oldPrice: initial?.oldPrice ?? '',
    stock: initial?.stock ?? '50',
  }));
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);
  const fileRef = useRef(null);
  const pickFile = async (e) => {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file) return;
    setUploading(true);
    try {
      const url = await onUpload(file);
      if (url) setP((s) => ({ ...s, image: url }));
    } finally {
      setUploading(false);
    }
  };
  const set = (k) => (e) => setP((s) => ({ ...s, [k]: e.target.type === 'checkbox' ? e.target.checked : e.target.value }));

  const submit = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      const ok = await onSave({
        name: p.name.trim(),
        nameAr: p.nameAr || null,
        category: p.category,
        price: parseFloat(p.price),
        oldPrice: p.oldPrice === '' ? null : parseFloat(p.oldPrice),
        stock: parseInt(p.stock, 10) || 0,
        debit: p.debit,
        warranty: p.warranty,
        description: p.description,
        image: p.image,
        isFeatured: p.isFeatured,
        showOnHome: p.showOnHome,
        pickupDiscount: p.pickupDiscount,
        isHero: p.isHero,
      });
      if (ok !== false) onClose();
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-slate-900/50 flex items-start sm:items-center justify-center p-4 overflow-y-auto">
      <form onSubmit={submit} className="bg-white rounded-2xl max-w-2xl w-full shadow-2xl my-4">
        <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between">
          <h3 className="font-black text-slate-900">{initial?.id ? 'Modifier le produit' : 'Nouveau produit'}</h3>
          <button type="button" onClick={onClose} className="p-2 hover:bg-slate-100 rounded-xl" aria-label="Fermer">
            <X className="w-4 h-4 text-slate-500" />
          </button>
        </div>
        <div className="p-5 grid grid-cols-1 sm:grid-cols-[140px_1fr] gap-5">
          <div className="space-y-2">
            <div className="aspect-square rounded-xl bg-slate-50 border border-slate-200 overflow-hidden">
              <img src={p.image} alt="" className="w-full h-full object-contain" />
            </div>
            <input ref={fileRef} type="file" accept="image/jpeg,image/png,image/webp" onChange={pickFile} className="hidden" />
            <button
              type="button"
              onClick={() => fileRef.current?.click()}
              disabled={uploading}
              className="w-full inline-flex items-center justify-center gap-1.5 px-3 py-2 bg-blue-50 hover:bg-blue-100 text-blue-700 rounded-xl text-xs font-bold disabled:opacity-60"
            >
              {uploading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Upload className="w-3.5 h-3.5" />}
              {uploading ? 'Envoi…' : 'Changer la photo'}
            </button>
            <select value={p.image} onChange={set('image')} className={`${inputCls} text-xs`} aria-label="Photo existante">
              {[...new Set([p.image, ...IMAGES])].map((img) => (
                <option key={img} value={img}>{img.replace('/products/', '')}</option>
              ))}
            </select>
            <p className="text-[10px] text-slate-400 leading-snug">JPG, PNG ou WEBP, 5 Mo max. Ou choisissez une photo déjà en ligne.</p>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="col-span-2">
              <label className="text-xs font-bold text-slate-600 block mb-1">Nom *</label>
              <input required value={p.name} onChange={set('name')} className={inputCls} />
            </div>
            <div className="col-span-2">
              <label className="text-xs font-bold text-slate-600 block mb-1">Nom en arabe</label>
              <input dir="rtl" value={p.nameAr || ''} onChange={set('nameAr')} className={inputCls} />
            </div>
            <div>
              <label className="text-xs font-bold text-slate-600 block mb-1">Prix (DT) *</label>
              <input required type="number" min="0" step="0.001" value={p.price} onChange={set('price')} className={inputCls} />
            </div>
            <div>
              <label className="text-xs font-bold text-slate-600 block mb-1">Ancien prix (barré)</label>
              <input type="number" min="0" step="0.001" value={p.oldPrice ?? ''} onChange={set('oldPrice')} className={inputCls} />
            </div>
            <div>
              <label className="text-xs font-bold text-slate-600 block mb-1">Stock</label>
              <input type="number" min="0" value={p.stock} onChange={set('stock')} className={inputCls} />
            </div>
            <div>
              <label className="text-xs font-bold text-slate-600 block mb-1">Catégorie</label>
              <select value={p.category} onChange={set('category')} className={inputCls}>
                {Object.entries(CATEGORIES).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
            </div>
            <div>
              <label className="text-xs font-bold text-slate-600 block mb-1">Débit</label>
              <input value={p.debit || ''} onChange={set('debit')} placeholder="4 L/min" className={inputCls} />
            </div>
            <div>
              <label className="text-xs font-bold text-slate-600 block mb-1">Garantie</label>
              <input value={p.warranty || ''} onChange={set('warranty')} className={inputCls} />
            </div>
            <div className="col-span-2">
              <label className="text-xs font-bold text-slate-600 block mb-1">Description</label>
              <textarea rows={3} value={p.description || ''} onChange={set('description')} className={`${inputCls} resize-none`} />
            </div>
            <label className="col-span-2 flex items-center gap-2 text-sm text-slate-700">
              <input type="checkbox" checked={!!p.isFeatured} onChange={set('isFeatured')} className="accent-blue-600 w-4 h-4" />
              Mettre en avant dans la boutique
            </label>
            <label className="col-span-2 flex items-center gap-2 text-sm text-slate-700">
              <input type="checkbox" checked={!!p.showOnHome} onChange={set('showOnHome')} className="accent-blue-600 w-4 h-4" />
              Afficher sur la page d'accueil
            </label>
            <label className="col-span-2 flex items-center gap-2 text-sm text-slate-700">
              <input type="checkbox" checked={!!p.pickupDiscount} onChange={set('pickupDiscount')} className="accent-blue-600 w-4 h-4" />
              Remise de 10% en retrait au local (sans frais de livraison)
            </label>
            <label className="col-span-2 flex items-center gap-2 text-sm text-slate-700">
              <input type="checkbox" checked={!!p.isHero} onChange={set('isHero')} className="accent-blue-600 w-4 h-4" />
              Produit vedette : grande carte en haut de la page d'accueil (un seul produit)
            </label>
          </div>
        </div>
        <div className="px-5 py-4 border-t border-slate-100 flex justify-end gap-2">
          <button type="button" onClick={onClose} className="px-4 py-2 border border-slate-200 rounded-xl text-sm font-bold text-slate-600 hover:bg-slate-50">
            Annuler
          </button>
          <button type="submit" disabled={saving} className="px-5 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-sm font-bold disabled:opacity-60">
            {saving ? 'Enregistrement…' : 'Enregistrer'}
          </button>
        </div>
      </form>
    </div>
  );
}

function FlagToggle({ on, onChange, icon: Icon, label }) {
  return (
    <button
      type="button"
      onClick={() => onChange(!on)}
      aria-pressed={on}
      title={label}
      className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[11px] font-bold border transition ${
        on ? 'bg-blue-600 border-blue-600 text-white' : 'bg-white border-slate-200 text-slate-400 hover:border-blue-300 hover:text-blue-600'
      }`}
    >
      <Icon className="w-3.5 h-3.5" /> {on ? 'Oui' : 'Non'}
    </button>
  );
}

function StockCell({ product, onSave }) {
  const [value, setValue] = useState(String(product.stock));
  const dirty = value !== String(product.stock);
  const tone = product.stock <= 10 ? 'text-red-600' : product.stock <= 25 ? 'text-amber-600' : 'text-slate-700';
  return (
    <div className="flex items-center justify-center gap-1" onClick={(e) => e.stopPropagation()}>
      <input
        type="number"
        min="0"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => e.key === 'Enter' && dirty && onSave(parseInt(value, 10) || 0)}
        className={`w-16 text-center border rounded-lg px-1 py-1 text-sm font-bold ${dirty ? 'border-blue-400' : 'border-transparent hover:border-slate-200'} ${tone}`}
        aria-label={`Stock ${product.name}`}
      />
      {dirty && (
        <button onClick={() => onSave(parseInt(value, 10) || 0)} className="px-2 py-1 bg-blue-600 text-white rounded-md text-[11px] font-bold">
          OK
        </button>
      )}
    </div>
  );
}

export function Products({ products, filter, setFilter, onCreate, onUpdate, onDelete, onUpload }) {
  const [query, setQuery] = useState('');
  const [editing, setEditing] = useState(null);

  const counts = useMemo(() => {
    const c = {
      all: products.length,
      low: products.filter((p) => p.stock <= 10).length,
      home: products.filter((p) => p.showOnHome).length,
      pickup: products.filter((p) => p.pickupDiscount).length,
    };
    products.forEach((p) => (c[p.category] = (c[p.category] || 0) + 1));
    return c;
  }, [products]);

  const filtered = products.filter((p) => {
    if (filter === 'low' && p.stock > 10) return false;
    if (filter === 'home' && !p.showOnHome) return false;
    if (filter === 'pickup' && !p.pickupDiscount) return false;
    if (!['all', 'low', 'home', 'pickup'].includes(filter) && p.category !== filter) return false;
    const q = query.trim().toLowerCase();
    return !q || p.name.toLowerCase().includes(q) || p.id.toLowerCase().includes(q);
  });

  return (
    <div className="space-y-4">
      <div className="flex flex-col lg:flex-row lg:items-center gap-3 justify-between">
        <FilterChips
          value={filter}
          onChange={setFilter}
          options={[
            { value: 'all', label: 'Tous', count: counts.all },
            { value: 'low', label: 'Stock faible', count: counts.low },
            { value: 'home', label: "Page d'accueil", count: counts.home },
            { value: 'pickup', label: 'Remise retrait', count: counts.pickup },
            ...Object.entries(CATEGORIES)
              .filter(([v]) => counts[v])
              .map(([v, l]) => ({ value: v, label: l, count: counts[v] })),
          ]}
        />
        <div className="flex gap-2">
          <SearchInput value={query} onChange={setQuery} placeholder="Rechercher un produit" icon={Search} />
          <button onClick={() => setEditing({})} className="inline-flex items-center gap-1.5 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-xs font-bold whitespace-nowrap">
            <Plus className="w-4 h-4" /> Ajouter
          </button>
        </div>
      </div>

      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
        {filtered.length === 0 ? (
          <EmptyState icon={Package} title="Aucun produit" />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm min-w-[920px]">
              <thead>
                <tr className="bg-slate-50 text-[11px] uppercase font-bold text-slate-500 border-b border-slate-200">
                  <th className="px-4 py-3 text-left">Produit</th>
                  <th className="px-4 py-3 text-left">Catégorie</th>
                  <th className="px-4 py-3 text-right">Prix</th>
                  <th className="px-4 py-3 text-center">Stock</th>
                  <th className="px-4 py-3 text-center">Page d'accueil</th>
                  <th className="px-4 py-3 text-center">-10% retrait</th>
                  <th className="px-4 py-3 text-center">Vedette</th>
                  <th className="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {filtered.map((p) => (
                  <tr key={p.id} className="hover:bg-slate-50">
                    <td className="px-4 py-2.5 cursor-pointer" onClick={() => setEditing(p)} title="Modifier photo, prix, description…">
                      <div className="flex items-center gap-3">
                        <img src={p.image} alt="" className="w-10 h-10 rounded-lg object-cover bg-slate-100 shrink-0" />
                        <div className="min-w-0">
                          <div className="font-semibold text-slate-900 truncate flex items-center gap-1.5">
                            {p.name}
                            {p.isFeatured && <Star className="w-3.5 h-3.5 text-amber-400 fill-amber-400 shrink-0" />}
                          </div>
                          <div className="text-[11px] text-slate-400">{p.debit || p.id}</div>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-2.5"><Badge tone="blue">{CATEGORIES[p.category] || p.category}</Badge></td>
                    <td className="px-4 py-2.5 text-right whitespace-nowrap">
                      <div className="font-bold tabular-nums">{dt(p.price, 2)}</div>
                      {p.oldPrice ? <div className="text-[11px] text-slate-400 line-through tabular-nums">{dt(p.oldPrice, 2)}</div> : null}
                    </td>
                    <td className="px-4 py-2.5">
                      <StockCell key={`${p.id}-${p.stock}`} product={p} onSave={(stock) => onUpdate(p.id, { stock })} />
                    </td>
                    <td className="px-4 py-2.5 text-center">
                      <FlagToggle on={!!p.showOnHome} icon={Home} label="Afficher sur la page d'accueil" onChange={(v) => onUpdate(p.id, { showOnHome: v })} />
                    </td>
                    <td className="px-4 py-2.5 text-center">
                      <FlagToggle on={!!p.pickupDiscount} icon={Store} label="Remise de 10% en retrait au local" onChange={(v) => onUpdate(p.id, { pickupDiscount: v })} />
                    </td>
                    <td className="px-4 py-2.5 text-center">
                      <FlagToggle on={!!p.isHero} icon={Sparkles} label="Produit vedette en haut de la page d'accueil" onChange={(v) => onUpdate(p.id, { isHero: v })} />
                    </td>
                    <td className="px-4 py-2.5 text-right whitespace-nowrap">
                      <button onClick={() => setEditing(p)} className="p-2 text-slate-500 hover:text-blue-700 hover:bg-blue-50 rounded-lg" title="Modifier">
                        <Edit3 className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => window.confirm(`Supprimer « ${p.name} » ? Cette action est définitive.`) && onDelete(p.id)}
                        className="p-2 text-slate-500 hover:text-red-600 hover:bg-red-50 rounded-lg"
                        title="Supprimer"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {editing && (
        <ProductModal
          initial={editing}
          onClose={() => setEditing(null)}
          onSave={(data) => (editing.id ? onUpdate(editing.id, data) : onCreate(data))}
          onUpload={onUpload}
        />
      )}
    </div>
  );
}
