import React, { useState } from 'react';
import { useCart } from '../context/CartContext';
import { ReferencesCarousel } from '../components/ReferencesCarousel';
import { SavingsCalculator } from '../components/SavingsCalculator';
import { 
  Droplets, 
  Flame, 
  ShieldCheck, 
  TrendingDown, 
  ArrowRight, 
  CheckCircle2, 
  Sparkles, 
  Star, 
  ShoppingBag, 
  Wrench, 
  Zap, 
  HelpCircle, 
  ChevronDown, 
  ChevronUp 
} from 'lucide-react';

export const HomePage = ({ setCurrentTab }) => {
  const { addToCart, language } = useCart();
  const [openFaq, setOpenFaq] = useState(null);

  // Quick packs for showcase
  const featuredPacks = [
    {
      id: 'pack-appartement-4l',
      name: 'Pack Appartement 4L',
      badge: 'Plus Populaire',
      price: 66.0,
      oldPrice: 78.0,
      image: '/products/bague_mousseur_complet.jpg',
      desc: 'Idéal Appartement F2 / F3 : 2 Mousseurs 4L/min + 1 Régulateur Douche + 1 Eco-Sac WC 3L + 1 Sac Débit-mètre Gratuit',
      features: ['Jusqu’à 60% d’économie d’eau', '+25% d’économie sur gaz STEG', 'Garantie 3 ans & Eco-Sac à vie', 'Sac Débit-mètre offert']
    },
    {
      id: 'pack-maison-4l',
      name: 'Pack Maison / Villa 4L',
      badge: 'Grand Logement',
      price: 109.0,
      oldPrice: 135.0,
      image: '/products/pomme_douche_chromee.jpg',
      desc: 'Équipement complet Villa : 4 Mousseurs 4L/min + 2 Régulateurs Douche/Toilette + 2 Eco-Sacs WC 3L + Débit-mètre',
      features: ['Idéal pour 4 à 8 personnes', 'Double salle de bain', 'Économie annuelle > 280 DT', 'Installation en 2 minutes']
    }
  ];

  // Clip diagram zones (from Pascal's email RETOUCHES CLIP)
  const clipZones = [
    {
      zone: 'Évier Cuisine',
      flow: '4 ou 5 L/min',
      waterSaved: '+60%',
      gasSaved: '+25%',
      img: '/products/bague_mousseur_complet.jpg',
      desc: 'Bague Inox + Cartouche Delrin anticalcaire.'
    },
    {
      zone: 'Lavabo Salle de Bain',
      flow: '4 L/min',
      waterSaved: '+60%',
      gasSaved: '+25%',
      img: '/products/cartouche_hydro_verte.jpg',
      desc: 'Jet doux aéré, supprime les éclaboussures.'
    },
    {
      zone: 'Douche & Flexible',
      flow: '5 ou 7 L/min',
      waterSaved: '+60%',
      gasSaved: '+25%',
      img: '/products/bague_mousseur_grille_bleue.jpg',
      desc: 'Régulateur Inox placé sous le flexible de douche.'
    },
    {
      zone: 'Toilettes & WC',
      flow: '3 Litres / chasse',
      waterSaved: '-30%',
      gasSaved: 'N/A',
      img: '/products/ecosac_wc_3l.jpg',
      desc: 'Eco-Sac 3L imputrescible suspendu dans le réservoir.'
    }
  ];

  // FAQ items
  const faqs = [
    {
      q: "Pourquoi la pression SONEDE fait-elle exploser la facture en Tunisie ?",
      a: "Contrairement à l'Europe où la pression est standardisée à 3 bars (12L/min au robinet), la pression SONEDE en Tunisie n'est pas régulée et varie selon les quartiers. Pour plus de 80% des foyers, cela crée un débit excessif atteignant 20 à 24 litres/minute ! Vous consommez et payez le double sans vous en rendre compte."
    },
    {
      q: "Est-ce qu'on perd du confort ou de la pression sous la douche ?",
      a: "Absolument pas ! Nos dispositifs hydro-économes intègrent un système d'aération breveté sous marque HOSTAFORM / DELRIN. L'eau est mélangée à de l'air sous pression, offrant un jet ferme, généreux et massant, tout en consommant 60% d'eau en moins."
    },
    {
      q: "Quel est l'impact direct sur la facture de gaz STEG ?",
      a: "Toute l'eau chaude utilisée sous la douche ou au robinet doit être chauffée par votre chaudière ou chauffe-eau à gaz STEG. En divisant par deux le volume d'eau chaude consommée, vous réduisez automatiquement de 25% à 40% la consommation de gaz nécessaire pour la chauffer !"
    },
    {
      q: "L'installation nécessite-t-elle un plombier ou des outils ?",
      a: "Non, aucun outil ni compétences en plomberie ne sont nécessaires. L'installation se fait en moins de 2 minutes en dévissant l'ancien embout à la main et en vissant le régulateur EcoPower."
    },
    {
      q: "Comment fonctionne la garantie et le paiement ?",
      a: "Tous nos dispositifs bénéficient d'une garantie constructeur de 3 ans (et garantie à vie pour l'Eco-Sac WC). Nous livrons partout en Tunisie sous 24-48h avec paiement en espèces à la livraison (Cash on Delivery). Vous disposez de 14 jours « Satisfait ou Remboursé »."
    }
  ];

  return (
    <div className="space-y-16 sm:space-y-24">
      
      {/* 1. HERO SECTION */}
      <section className="relative overflow-hidden pt-8 pb-16 sm:pt-16 sm:pb-24 bg-gradient-to-b from-brand-50/60 via-white to-slate-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 items-center">
            
            {/* Left Column: Copy & CTAs */}
            <div className="lg:col-span-7 space-y-6 text-center lg:text-left">
              
              <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-brand-100 text-brand-800 text-xs font-bold tracking-wide">
                <Sparkles className="w-4 h-4 text-brand-600" />
                <span>Leader en Tunisie • Normes ISO &amp; ACS Certifiées</span>
              </div>

              <h1 className="text-4xl sm:text-5xl lg:text-6xl font-black text-slate-900 tracking-tight leading-[1.15] font-serif">
                Réduisez votre facture <span className="text-brand-700">SONEDE &amp; STEG</span> jusqu’à <span className="text-energy-500">60%</span>
              </h1>

              <p className="text-base sm:text-lg text-slate-600 leading-relaxed max-w-2xl mx-auto lg:mx-0">
                La solution hydro-économe certifiée Delrin/Hostaform qui régule la pression en Tunisie. Même confort de jet, deux fois moins d’eau et de gaz consommés. Livré chez vous en 24h avec certificat de garantie 3 ans.
              </p>

              {/* CTAs */}
              <div className="flex flex-col sm:flex-row items-center justify-center lg:justify-start gap-3 pt-2">
                <button
                  onClick={() => setCurrentTab('shop')}
                  className="w-full sm:w-auto bg-gradient-to-r from-energy-500 to-energy-600 hover:from-energy-600 hover:to-energy-500 text-white font-extrabold px-8 py-4 rounded-2xl text-base shadow-xl shadow-energy-500/30 flex items-center justify-center gap-2 transition-all hover:scale-105 active:scale-95"
                >
                  <ShoppingBag className="w-5 h-5" />
                  <span>Commander un Pack Éco</span>
                </button>

                <button
                  onClick={() => setCurrentTab('calculator')}
                  className="w-full sm:w-auto bg-white hover:bg-slate-50 text-slate-800 border-2 border-slate-200 font-bold px-7 py-4 rounded-2xl text-base flex items-center justify-center gap-2 transition-all hover:border-brand-500 hover:text-brand-700"
                >
                  <span>Simuler mes économies</span>
                  <ArrowRight className="w-4 h-4" />
                </button>
              </div>

              {/* Trust bullets */}
              <div className="pt-4 grid grid-cols-3 gap-2 border-t border-slate-200/80 text-center lg:text-left">
                <div>
                  <div className="text-xl sm:text-2xl font-black text-brand-800">+60%</div>
                  <div className="text-[11px] text-slate-500 font-semibold">Économie d'eau</div>
                </div>
                <div>
                  <div className="text-xl sm:text-2xl font-black text-energy-500">+25%</div>
                  <div className="text-[11px] text-slate-500 font-semibold">Économie gaz STEG</div>
                </div>
                <div>
                  <div className="text-xl sm:text-2xl font-black text-blue-600">3 Ans</div>
                  <div className="text-[11px] text-slate-500 font-semibold">Garantie &amp; Certificat</div>
                </div>
              </div>

            </div>

            {/* Right Column: Hero Visual Product Card */}
            <div className="lg:col-span-5 relative">
              <div className="relative mx-auto max-w-md bg-white rounded-3xl p-6 shadow-2xl border border-slate-200/90 overflow-hidden">
                <div className="absolute top-4 right-4 bg-energy-500 text-white text-[10px] font-black uppercase px-3 py-1 rounded-full shadow-xs">
                  Offre Spéciale -15%
                </div>

                <div className="text-xs font-bold text-brand-700 uppercase tracking-wider mb-2">
                  Solution N°1 en Tunisie
                </div>
                <h3 className="text-2xl font-black text-slate-900 font-serif">
                  Pack Appartement Éco 4L
                </h3>
                <p className="text-xs text-slate-500 mt-1">
                  2 Mousseurs Robinets + 1 Régulateur Douche + 1 Eco-Sac WC 3L
                </p>

                <div className="my-5 rounded-2xl bg-slate-50 p-4 border border-slate-100 flex items-center justify-center">
                  <img
                    src="/products/bague_mousseur_complet.jpg"
                    alt="Pack EcoPower"
                    className="h-52 object-contain drop-shadow-md hover:scale-105 transition-transform"
                  />
                </div>

                <div className="flex items-baseline justify-between mb-4">
                  <div>
                    <span className="text-xs text-slate-400 line-through mr-2">78.000 DT</span>
                    <span className="text-3xl font-black text-brand-900">66.000 DT</span>
                    <span className="text-xs text-slate-500 ml-1">TTC</span>
                  </div>
                  <span className="text-xs font-bold text-blue-700 bg-blue-50 px-2.5 py-1 rounded-md">
                    Sac Débitmètre Offert
                  </span>
                </div>

                <button
                  onClick={() => addToCart({
                    id: 'pack-appartement-4l',
                    name: 'Pack Appartement 4 Litres',
                    price: 66.0,
                    image: '/products/bague_mousseur_complet.jpg'
                  })}
                  className="w-full bg-brand-700 hover:bg-brand-800 text-white font-black py-3 px-4 rounded-xl text-sm flex items-center justify-center gap-2 shadow-md shadow-brand-700/20 transition-all hover:scale-[1.02]"
                >
                  <ShoppingBag className="w-4 h-4" />
                  <span>Ajouter au Panier (66 DT)</span>
                </button>

                <p className="text-center text-[11px] text-slate-600 mt-3 flex items-center justify-center gap-1.5">
                  <CheckCircle2 className="w-3.5 h-3.5 text-blue-600" />
                  Paiement à la livraison • Satisfait ou remboursé 14 jours
                </p>
              </div>
            </div>

          </div>
        </div>
      </section>

      {/* 2. SCHÉMA CLIP & ZONES D'INSTALLATION (Demandé par Pascal Fabre) */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center max-w-3xl mx-auto mb-12">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-skywater-100 text-skywater-800 text-xs font-bold uppercase tracking-wider mb-3">
            <Zap className="w-4 h-4 text-skywater-600" />
            <span>Installation Rapide Sans Outils</span>
          </div>
          <h2 className="text-3xl sm:text-4xl font-extrabold text-slate-900 font-serif">
            Où installer les économiseurs dans votre logement ?
          </h2>
          <p className="text-slate-600 text-sm sm:text-base mt-2">
            Chaque point d'eau de votre maison peut être équipé en moins de 2 minutes pour stopper le gaspillage mécanique SONEDE.
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
          {clipZones.map((item, idx) => (
            <div
              key={idx}
              className="bg-white rounded-3xl border border-slate-200/80 p-5 shadow-xs hover:shadow-xl transition-all duration-300 flex flex-col justify-between group hover:-translate-y-1"
            >
              <div>
                <div className="h-44 rounded-2xl bg-slate-50 border border-slate-100 flex items-center justify-center p-3 mb-4 overflow-hidden">
                  <img
                    src={item.img}
                    alt={item.zone}
                    className="max-h-full max-w-full object-contain group-hover:scale-105 transition-transform duration-300"
                  />
                </div>

                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-bold px-2 py-0.5 rounded-md bg-brand-50 text-brand-700">
                    Débit : {item.flow}
                  </span>
                  <span className="text-[10px] font-black text-slate-400">Étape {idx + 1}</span>
                </div>

                <h3 className="font-extrabold text-base text-slate-900 mb-1">{item.zone}</h3>
                <p className="text-xs text-slate-500 leading-relaxed mb-4">{item.desc}</p>
              </div>

              {/* Savings badges */}
              <div className="pt-3 border-t border-slate-100 grid grid-cols-2 gap-2 text-center text-xs">
                <div className="bg-skywater-50 text-skywater-800 p-2 rounded-xl">
                  <div className="font-black text-sm text-skywater-700">{item.waterSaved}</div>
                  <div className="text-[10px] font-semibold text-slate-500">Économie Eau</div>
                </div>
                <div className="bg-amber-50 text-amber-900 p-2 rounded-xl">
                  <div className="font-black text-sm text-energy-600">{item.gasSaved}</div>
                  <div className="text-[10px] font-semibold text-slate-500">Économie Gaz</div>
                </div>
              </div>

            </div>
          ))}
        </div>
      </section>

      {/* 3. SIMULATEUR D'ÉCONOMIES INTERACTIF */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <SavingsCalculator onSelectPack={(packId) => {
          if (packId === 'pack-appartement-4l') {
            addToCart({
              id: 'pack-appartement-4l',
              name: 'Pack Appartement 4 Litres',
              price: 66.0,
              image: '/products/bague_mousseur_complet.jpg'
            });
          } else {
            addToCart({
              id: 'pack-maison-4l',
              name: 'Pack Maison / Villa 4 Litres',
              price: 109.0,
              image: '/products/pomme_douche_chromee.jpg'
            });
          }
        }} />
      </section>

      {/* 4. PACKS VEDETTES DU SITE */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-end mb-8 gap-4">
          <div>
            <div className="text-xs font-bold text-brand-700 uppercase tracking-wider mb-1">
              Les Meilleures Ventes
            </div>
            <h2 className="text-3xl font-black text-slate-900 font-serif">
              Choisissez votre Pack Éco-Énergie
            </h2>
          </div>
          <button
            onClick={() => setCurrentTab('shop')}
            className="text-xs font-bold text-brand-700 hover:text-brand-900 flex items-center gap-1 group"
          >
            <span>Voir toute la boutique au détail</span>
            <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
          </button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          {featuredPacks.map((pack) => (
            <div
              key={pack.id}
              className="bg-white rounded-3xl border border-slate-200/90 p-6 sm:p-8 shadow-md hover:shadow-xl transition-all flex flex-col justify-between"
            >
              <div>
                <div className="flex justify-between items-start mb-4">
                  <span className="px-3 py-1 bg-brand-100 text-brand-800 text-xs font-bold rounded-full">
                    {pack.badge}
                  </span>
                  <div className="flex items-center gap-1 text-amber-400">
                    <Star className="w-4 h-4 fill-amber-400" />
                    <span className="text-xs font-black text-slate-800">4.9 / 5</span>
                  </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-12 gap-6 items-center mb-6">
                  <div className="sm:col-span-5 h-44 rounded-2xl bg-slate-50 border border-slate-100 flex items-center justify-center p-3">
                    <img
                      src={pack.image}
                      alt={pack.name}
                      className="max-h-full max-w-full object-contain"
                    />
                  </div>
                  <div className="sm:col-span-7">
                    <h3 className="text-xl font-black text-slate-900 font-serif">{pack.name}</h3>
                    <p className="text-xs text-slate-600 mt-1 leading-relaxed">{pack.desc}</p>
                    <div className="mt-3">
                      <span className="text-xs text-slate-400 line-through mr-2">{pack.oldPrice.toFixed(3)} DT</span>
                      <span className="text-2xl font-black text-brand-800">{pack.price.toFixed(3)} DT</span>
                    </div>
                  </div>
                </div>

                <div className="space-y-2 mb-6 text-xs text-slate-700">
                  {pack.features.map((feat, fidx) => (
                    <div key={fidx} className="flex items-center gap-2">
                      <CheckCircle2 className="w-4 h-4 text-blue-600 shrink-0" />
                      <span>{feat}</span>
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
                className="w-full bg-gradient-to-r from-energy-500 to-energy-600 hover:from-energy-600 hover:to-energy-500 text-white font-black py-3.5 px-4 rounded-xl text-sm flex items-center justify-center gap-2 shadow-md shadow-energy-500/25 transition-all hover:scale-[1.01]"
              >
                <ShoppingBag className="w-4 h-4" />
                <span>Ajouter au Panier ({pack.price.toFixed(3)} DT)</span>
              </button>
            </div>
          ))}
        </div>
      </section>

      {/* 5. CARROUSEL DES RÉFÉRENCES (Hotels, Cliniques, etc.) */}
      <ReferencesCarousel />

      {/* 6. FAQ ACCORDION */}
      <section className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center mb-10">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-slate-100 text-slate-700 text-xs font-bold uppercase tracking-wider mb-2">
            <HelpCircle className="w-4 h-4 text-brand-600" />
            <span>Foire Aux Questions</span>
          </div>
          <h2 className="text-3xl font-extrabold text-slate-900 font-serif">
            Tout ce qu'il faut savoir sur l'hydro-économie
          </h2>
        </div>

        <div className="space-y-3">
          {faqs.map((faq, idx) => {
            const isOpen = openFaq === idx;
            return (
              <div
                key={idx}
                className="bg-white rounded-2xl border border-slate-200/80 overflow-hidden shadow-xs transition"
              >
                <button
                  onClick={() => setOpenFaq(isOpen ? null : idx)}
                  className="w-full text-left p-5 flex items-center justify-between gap-4 font-bold text-sm sm:text-base text-slate-900 hover:text-brand-700 transition"
                >
                  <span>{faq.q}</span>
                  {isOpen ? <ChevronUp className="w-5 h-5 text-brand-600 shrink-0" /> : <ChevronDown className="w-5 h-5 text-slate-400 shrink-0" />}
                </button>
                {isOpen && (
                  <div className="px-5 pb-5 text-xs sm:text-sm text-slate-600 leading-relaxed border-t border-slate-100 pt-3">
                    {faq.a}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </section>

      {/* 7. FINAL CALL TO ACTION */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pb-10">
        <div className="bg-gradient-to-br from-brand-900 via-brand-800 to-skywater-700 text-white rounded-3xl p-8 sm:p-14 text-center relative overflow-hidden shadow-2xl">
          <div className="relative z-10 max-w-2xl mx-auto space-y-5">
            <span className="px-3.5 py-1.5 rounded-full bg-white/10 backdrop-blur-md text-sky-300 text-xs font-bold uppercase tracking-wider border border-white/20">
              Livraison 24-48h Partout en Tunisie
            </span>
            <h2 className="text-3xl sm:text-5xl font-black font-serif tracking-tight text-white">
              Passez à l’Hydro-Économie Dès Aujourd’hui
            </h2>
            <p className="text-slate-200 text-sm sm:text-base">
              Rejoignez plus de 2 000 foyers et 100 établissements équipés. Vos factures SONEDE et STEG diminuent dès le premier jour d'installation.
            </p>
            <div className="pt-2 flex flex-col sm:flex-row items-center justify-center gap-3">
              <button
                onClick={() => setCurrentTab('shop')}
                className="w-full sm:w-auto bg-gradient-to-r from-energy-500 to-energy-600 hover:from-energy-600 hover:to-energy-500 text-white font-extrabold px-8 py-4 rounded-2xl text-base shadow-xl transition-all hover:scale-105"
              >
                Commander Mon Pack en Ligne
              </button>
              <button
                onClick={() => setCurrentTab('professionnels')}
                className="w-full sm:w-auto bg-white/10 hover:bg-white/20 text-white border border-white/30 font-bold px-7 py-4 rounded-2xl text-base transition"
              >
                Espace Professionnel &amp; Devis
              </button>
            </div>
            <div className="pt-4 text-xs text-slate-300 flex items-center justify-center gap-3">
              <span>✅ Garantie 3 ans</span>
              <span>•</span>
              <span>✅ Satisfait ou Remboursé 14 jours</span>
              <span>•</span>
              <span>✅ Paiement à la livraison</span>
            </div>
          </div>
        </div>
      </section>

    </div>
  );
};
