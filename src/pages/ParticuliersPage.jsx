import React from 'react';
import { useCart } from '../context/CartContext';
import { SavingsCalculator } from '../components/SavingsCalculator';
import { 
  Droplets, 
  Flame, 
  ShieldCheck, 
  CheckCircle2, 
  ShoppingBag, 
  ArrowRight, 
  Gift, 
  Sparkles,
  AlertTriangle
} from 'lucide-react';

export const ParticuliersPage = ({ setCurrentTab }) => {
  const { addToCart, language } = useCart();

  const packs = [
    {
      id: 'pack-appartement-4l',
      name: 'Pack Appartement 4 Litres',
      price: 66.0,
      oldPrice: 78.0,
      debit: '4 L/min (Robinets) • 5 L/min (Douche)',
      idealFor: 'Appartement S+1, S+2 ou S+3 (1 Salle de Bain)',
      image: '/products/bague_mousseur_complet.jpg',
      composition: [
        '2x Hydro-économes 4L/min pour robinets (cuisine + lavabo)',
        '1x Régulateur Inox 5L/min pour flexible de douche',
        '1x Eco-Sac WC 3 Litres imputrescible (garanti à vie)',
        '1x Sac Débit-Mètre gradué offert gratuitement'
      ]
    },
    {
      id: 'pack-appartement-5l',
      name: 'Pack Appartement 5 Litres',
      price: 66.0,
      oldPrice: 78.0,
      debit: '5 L/min (Robinets) • 7 L/min (Douche)',
      idealFor: 'Appartement recherchant un débit plus abondant',
      image: '/products/cartouche_hydro_verte_paire.jpg',
      composition: [
        '2x Hydro-économes 5L/min pour robinets',
        '1x Régulateur Inox 7L/min pour flexible de douche',
        '1x Eco-Sac WC 3 Litres imputrescible (garanti à vie)',
        '1x Sac Débit-Mètre gradué offert gratuitement'
      ]
    },
    {
      id: 'pack-maison-4l',
      name: 'Pack Maison / Villa 4 Litres',
      price: 109.0,
      oldPrice: 135.0,
      debit: '4 L/min (Robinets) • 5 L/min (Douches)',
      idealFor: 'Villa, Étage de villa ou Maison avec 2 salles de bain',
      image: '/products/pomme_douche_chromee.jpg',
      composition: [
        '4x Hydro-économes 4L/min pour robinets',
        '2x Régulateurs Inox pour douches et sanitaires',
        '2x Eco-Sacs WC 3 Litres imputrescibles (garantis à vie)',
        '1x Sac Débit-Mètre gradué offert gratuitement'
      ]
    },
    {
      id: 'pack-maison-5l',
      name: 'Pack Maison / Villa 5 Litres',
      price: 109.0,
      oldPrice: 135.0,
      debit: '5 L/min (Robinets) • 7 L/min (Douches)',
      idealFor: 'Grande famille / Villa avec fort besoin d’utilisation',
      image: '/products/ecosac_wc_3l.jpg',
      composition: [
        '4x Hydro-économes 5L/min pour robinets',
        '2x Régulateurs Inox pour douches 7L/min',
        '2x Eco-Sacs WC 3 Litres imputrescibles (garantis à vie)',
        '1x Sac Débit-Mètre gradué offert gratuitement'
      ]
    }
  ];

  return (
    <div className="py-10 space-y-16 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      
      {/* Header Banner */}
      <div className="bg-gradient-to-r from-brand-900 via-brand-800 to-skywater-600 text-white rounded-3xl p-8 sm:p-12 shadow-xl relative overflow-hidden">
        <div className="max-w-3xl space-y-4">
          <span className="px-3.5 py-1 bg-white/10 rounded-full text-emerald-300 text-xs font-bold uppercase tracking-wider border border-white/20">
            Espace Particuliers &amp; Foyers
          </span>
          <h1 className="text-3xl sm:text-5xl font-black font-serif tracking-tight text-white leading-tight">
            Rajoutez du Pouvoir d’Achat à Votre Famille
          </h1>
          <p className="text-slate-200 text-base sm:text-lg leading-relaxed">
            En économisant l'eau (SONEDE) et son chauffage au gaz (STEG). Découvrez pourquoi plus de 80% des foyers tunisiens surconsomment inutilement et comment y remédier en 2 minutes.
          </p>
        </div>
      </div>

      {/* The SONEDE Problem Explanation (from Pascal's docx) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-center bg-white rounded-3xl p-6 sm:p-10 border border-slate-200 shadow-md">
        
        <div className="lg:col-span-7 space-y-4">
          <div className="inline-flex items-center gap-2 text-amber-700 bg-amber-50 px-3 py-1 rounded-md text-xs font-bold">
            <AlertTriangle className="w-4 h-4" />
            <span>Le problème méconnu de la pression en Tunisie</span>
          </div>

          <h2 className="text-2xl sm:text-3xl font-extrabold text-slate-900 font-serif">
            Pourquoi payez-vous le double sur vos factures d’eau et de gaz ?
          </h2>

          <div className="space-y-3 text-slate-600 text-sm leading-relaxed">
            <p>
              En Europe, la pression d'eau est normalisée à <strong>3 Bars</strong>, délivrant en moyenne 12 litres/min pour un robinet et 16 litres/min pour une douche.
            </p>
            <p className="p-3 bg-red-50 border-l-4 border-red-500 rounded-r-xl text-red-900">
              <strong>En Tunisie, la pression de base SONEDE n’est pas normalisée.</strong> Cela engendre pour plus de 80% des utilisateurs une surconsommation d'eau pouvant atteindre <strong>le double par minute</strong> (20 à 24 litres/min !).
            </p>
            <p>
              Cette surconsommation mécanique entraîne immédiatement une surconsommation de <strong>Gaz (STEG)</strong> pour le chauffage de l'eau, ainsi qu’un passage dans les <strong>tranches tarifaires SONEDE supérieures</strong> beaucoup plus onéreuses.
            </p>
          </div>

          <div className="pt-2 flex flex-wrap gap-4 text-xs font-bold text-slate-700">
            <span className="flex items-center gap-1 text-brand-700">
              <CheckCircle2 className="w-4 h-4 text-emerald-600" /> Régulation à 4 ou 5 L/min robinets
            </span>
            <span className="flex items-center gap-1 text-brand-700">
              <CheckCircle2 className="w-4 h-4 text-emerald-600" /> Régulation à 5 ou 7 L/min douches
            </span>
            <span className="flex items-center gap-1 text-brand-700">
              <CheckCircle2 className="w-4 h-4 text-emerald-600" /> Garantie 3 ans Hostaform
            </span>
          </div>
        </div>

        {/* Gift debitmeter highlight */}
        <div className="lg:col-span-5 bg-gradient-to-br from-emerald-50 to-teal-50 border-2 border-dashed border-emerald-300 rounded-2xl p-6 text-center space-y-4">
          <div className="w-14 h-14 rounded-2xl bg-emerald-600 text-white flex items-center justify-center mx-auto shadow-md">
            <Gift className="w-7 h-7" />
          </div>
          <div>
            <span className="text-[11px] font-black uppercase text-emerald-800 tracking-wider">Cadeau Exclusif EcoPower</span>
            <h3 className="text-xl font-black text-emerald-950 mt-1">Sac Débit-Mètre Offert</h3>
            <p className="text-xs text-emerald-800 mt-2 leading-relaxed">
              Un sac débit-mètre gradué vous sera livré <strong>gratuitement</strong> avec chaque Pack Appartement ou Maison. Il vous permet de mesurer votre consommation en 10 secondes sous votre robinet avant et après l'installation !
            </p>
          </div>
          <div className="p-3 bg-white rounded-xl text-xs font-bold text-emerald-900 border border-emerald-100">
            Testez et constatez vos économies en direct chez vous !
          </div>
        </div>

      </div>

      {/* Calculator for consumers */}
      <SavingsCalculator onSelectPack={(packId) => {
        const found = packs.find(p => p.id === packId) || packs[0];
        addToCart({
          id: found.id,
          name: found.name,
          price: found.price,
          image: found.image
        });
      }} />

      {/* Packs Showcase */}
      <div className="space-y-8">
        <div className="text-center max-w-2xl mx-auto">
          <h2 className="text-3xl font-extrabold text-slate-900 font-serif">
            Les Packs Ecopower pour Particuliers
          </h2>
          <p className="text-slate-600 text-sm mt-2">
            Prêts à l'emploi • Se vissent à la main sans outils • Garantie 3 ans • Écosac garanti à vie
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          {packs.map((pack) => (
            <div
              key={pack.id}
              className="bg-white rounded-3xl border border-slate-200/90 p-6 sm:p-8 shadow-sm hover:shadow-xl transition-all flex flex-col justify-between"
            >
              <div>
                <div className="flex justify-between items-baseline mb-4">
                  <h3 className="font-extrabold text-xl text-slate-900 font-serif">{pack.name}</h3>
                  <div className="text-right">
                    <span className="text-xs text-slate-400 line-through mr-1.5">{pack.oldPrice.toFixed(3)} DT</span>
                    <span className="text-2xl font-black text-brand-800">{pack.price.toFixed(3)} DT</span>
                  </div>
                </div>

                <div className="h-44 rounded-2xl bg-slate-50 border border-slate-100 flex items-center justify-center p-4 mb-5">
                  <img
                    src={pack.image}
                    alt={pack.name}
                    className="max-h-full max-w-full object-contain hover:scale-105 transition-transform"
                  />
                </div>

                <div className="p-3 bg-brand-50/60 rounded-xl text-xs font-semibold text-brand-900 mb-4">
                  📍 {pack.idealFor}
                </div>

                <div className="space-y-2 mb-6">
                  <span className="text-xs font-bold text-slate-700 uppercase tracking-wider block">
                    Composition du pack :
                  </span>
                  {pack.composition.map((item, idx) => (
                    <div key={idx} className="flex items-start gap-2 text-xs text-slate-600">
                      <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                      <span>{item}</span>
                    </div>
                  ))}
                </div>
              </div>

              <button
                onClick={() => addToCart({
                  id: pack.id,
                  name: pack.name,
                  price: pack.price,
                  image: pack.image
                })}
                className="w-full bg-gradient-to-r from-energy-500 to-energy-600 hover:from-energy-600 hover:to-energy-500 text-white font-extrabold py-3.5 px-4 rounded-xl text-sm flex items-center justify-center gap-2 shadow-md shadow-energy-500/25 transition-all hover:scale-[1.01]"
              >
                <ShoppingBag className="w-4 h-4" />
                <span>Ajouter ce Pack au Panier ({pack.price.toFixed(3)} DT)</span>
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* Individual products CTA banner */}
      <div className="bg-slate-100 rounded-3xl p-8 border border-slate-200 text-center space-y-4">
        <h3 className="text-xl font-bold text-slate-800">
          Vous préférez acheter vos régulateurs ou accessoires à l’unité ?
        </h3>
        <p className="text-xs text-slate-600 max-w-xl mx-auto">
          Retrouvez nos bagues inox, nos cartouches hydro-économes de 2L à 5L/min, nos pommes de douche massantes et nos ampoules LED à détection dans notre boutique complète.
        </p>
        <button
          onClick={() => setCurrentTab('shop')}
          className="bg-brand-700 hover:bg-brand-800 text-white font-bold py-3 px-8 rounded-xl text-sm transition shadow-md shadow-brand-700/20"
        >
          Accéder à la Boutique au Détail
        </button>
      </div>

    </div>
  );
};
