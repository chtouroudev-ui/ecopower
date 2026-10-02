import React from 'react';
import { Droplets, Phone, Mail, MapPin, ShieldCheck, Truck, RefreshCw, Award } from 'lucide-react';
import { useCart } from '../context/CartContext';

export const Footer = ({ setCurrentTab }) => {
  const { language } = useCart();

  return (
    <footer className="bg-slate-900 text-slate-300 pt-16 pb-12 border-t border-slate-800">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        
        {/* Value props bar */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 pb-12 border-b border-slate-800 text-center md:text-left">
          <div className="flex items-center gap-4 justify-center md:justify-start">
            <div className="w-12 h-12 rounded-2xl bg-blue-950/80 text-blue-400 flex items-center justify-center shrink-0 border border-blue-800/40">
              <ShieldCheck className="w-6 h-6" />
            </div>
            <div>
              <h4 className="font-bold text-white text-sm">Garantie 3 Ans</h4>
              <p className="text-xs text-slate-400">Eco-Sac WC garanti à vie</p>
            </div>
          </div>

          <div className="flex items-center gap-4 justify-center md:justify-start">
            <div className="w-12 h-12 rounded-2xl bg-blue-950/80 text-sky-400 flex items-center justify-center shrink-0 border border-blue-800/40">
              <RefreshCw className="w-6 h-6" />
            </div>
            <div>
              <h4 className="font-bold text-white text-sm">Satisfait ou Remboursé</h4>
              <p className="text-xs text-slate-400">14 jours pour tester chez vous</p>
            </div>
          </div>

          <div className="flex items-center gap-4 justify-center md:justify-start">
            <div className="w-12 h-12 rounded-2xl bg-blue-950/80 text-blue-300 flex items-center justify-center shrink-0 border border-blue-800/40">
              <Truck className="w-6 h-6" />
            </div>
            <div>
              <h4 className="font-bold text-white text-sm">Livraison Partout en Tunisie</h4>
              <p className="text-xs text-slate-400">24 à 48h - Paiement à la livraison</p>
            </div>
          </div>

          <div className="flex items-center gap-4 justify-center md:justify-start">
            <div className="w-12 h-12 rounded-2xl bg-blue-950/80 text-blue-400 flex items-center justify-center shrink-0 border border-blue-800/40">
              <Award className="w-6 h-6" />
            </div>
            <div>
              <h4 className="font-bold text-white text-sm">Normes ISO &amp; ACS</h4>
              <p className="text-xs text-slate-400">Tenue prouvée jusqu'à 25 bars</p>
            </div>
          </div>
        </div>

        {/* Main Footer Content */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-10 py-12">
          
          {/* Brand info */}
          <div className="space-y-4">
            <div className="flex items-center gap-2">
              <div className="w-9 h-9 rounded-xl bg-blue-600 flex items-center justify-center text-white shadow-md shadow-blue-500/20">
                <Droplets className="w-5 h-5" />
              </div>
              <span className="font-extrabold text-xl text-white tracking-tight">ECO<span className="text-blue-400">POWER</span></span>
            </div>
            <p className="text-xs text-slate-400 leading-relaxed">
              Leader des solutions hydro-économes et de maîtrise énergétique en Tunisie. Nous accompagnons foyers, hôtels, cliniques et entreprises dans la réduction concrète de leurs factures SONEDE &amp; STEG.
            </p>
            <div className="text-xs text-slate-400 font-mono">
              Société ECOGAM SARL • ECEAU-LOGIS
            </div>
          </div>

          {/* Quick links */}
          <div>
            <h5 className="font-bold text-white text-sm uppercase tracking-wider mb-4">Navigation</h5>
            <ul className="space-y-2 text-xs">
              <li>
                <button onClick={() => setCurrentTab('home')} className="hover:text-blue-400 transition">Accueil</button>
              </li>
              <li>
                <button onClick={() => setCurrentTab('particuliers')} className="hover:text-blue-400 transition">Particuliers &amp; Résidentiel</button>
              </li>
              <li>
                <button onClick={() => setCurrentTab('professionnels')} className="hover:text-blue-400 transition">Professionnels B2B &amp; Hôtels</button>
              </li>
              <li>
                <button onClick={() => setCurrentTab('shop')} className="hover:text-blue-400 transition">Boutique &amp; Packs</button>
              </li>
              <li>
                <button onClick={() => setCurrentTab('calculator')} className="hover:text-blue-400 transition">Simulateur d'Économies</button>
              </li>
              <li>
                <button onClick={() => setCurrentTab('tracking')} className="hover:text-blue-400 transition">Suivi de Commande</button>
              </li>
              <li>
                <button onClick={() => setCurrentTab('references')} className="hover:text-blue-400 transition">Références Clients (+100)</button>
              </li>
            </ul>
          </div>

          {/* Gamme Produits */}
          <div>
            <h5 className="font-bold text-white text-sm uppercase tracking-wider mb-4">Gamme Phare</h5>
            <ul className="space-y-2 text-xs text-slate-400">
              <li>Pack Appartement 4L / 5L (66 DT)</li>
              <li>Pack Maison / Villa 4L / 5L (109 DT)</li>
              <li>Hydro-Économes Delrin 2L à 5L/min</li>
              <li>Régulateurs Inox Douche &amp; Flexible</li>
              <li>Pommes de Douche Massantes &amp; Anticalcaire</li>
              <li>Eco-Sac WC 3L (Garantie à vie)</li>
              <li>Ampoules LED à détection PIR</li>
            </ul>
          </div>

          {/* Contact */}
          <div>
            <h5 className="font-bold text-white text-sm uppercase tracking-wider mb-4">Contact &amp; Assistance</h5>
            <ul className="space-y-3 text-xs text-slate-400">
              <li className="flex items-start gap-2.5">
                <MapPin className="w-4 h-4 text-blue-400 shrink-0 mt-0.5" />
                <span>Tunis / Sousse / Sfax — Service technique national</span>
              </li>
              <li className="flex items-center gap-2.5">
                <Phone className="w-4 h-4 text-blue-400 shrink-0" />
                <a href="tel:+21671000000" className="hover:text-white transition">+216 71 000 000 / +216 98 000 000</a>
              </li>
              <li className="flex items-center gap-2.5">
                <Mail className="w-4 h-4 text-blue-400 shrink-0" />
                <a href="mailto:contact@eco-power.tn" className="hover:text-white transition">contact@eco-power.tn / eceau-lo@orange.fr</a>
              </li>
              <li className="pt-2">
                <button
                  onClick={() => setCurrentTab('admin')}
                  className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-blue-900 text-slate-300 hover:text-white text-[11px] font-bold transition flex items-center gap-1.5"
                >
                  <span>Accès Administration</span>
                </button>
              </li>
            </ul>
          </div>

        </div>

        {/* Bottom copyright */}
        <div className="pt-8 border-t border-slate-800 text-center text-xs text-slate-500 flex flex-col sm:flex-row justify-between items-center gap-4">
          <p>© 2026 ECOPOWER TUNISIE. Tous droits réservés.</p>
          <p className="text-slate-500">
            Solutions certifiées ISO 9001 &amp; ACS pour l'hôtellerie, la santé et le résidentiel.
          </p>
        </div>

      </div>
    </footer>
  );
};
