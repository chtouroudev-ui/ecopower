import React, { useState } from 'react';
import { Building2, Hotel, Hospital, GraduationCap, Award, CheckCircle2 } from 'lucide-react';
import { useCart } from '../context/CartContext';

export const ReferencesCarousel = () => {
  const { language } = useCart();
  const [activeTab, setActiveTab] = useState('hotels');

  // Categories
  const categories = [
    { id: 'hotels', label: language === 'ar' ? 'أكثر من 100 فندق' : '+100 Hôtels en Tunisie', icon: Hotel, count: 51 },
    { id: 'cliniques', label: language === 'ar' ? '+60% من المصحات' : '+60% des Cliniques', icon: Hospital, count: 7 },
    { id: 'entreprises', label: language === 'ar' ? 'شركات وبنوك' : 'Banques & Entreprises', icon: Building2, count: 13 },
    { id: 'universites', label: language === 'ar' ? 'جامعات ومبيتات' : 'Universités & Foyers', icon: GraduationCap, count: 5 },
  ];

  // Specific highlighted clinics extracted from docx
  const clinicNames = [
    "Clinique Les Oliviers (Sousse)",
    "Polyclinique Al Hakim (Nabeul)",
    "Clinique Hamda Laouani (Kairouan)",
    "Clinique Essalem (Sousse)",
    "Polyclinique Le Bardo (Tunis)"
  ];

  const hotelHighlights = [
    "Groupe El Mouradi Hotels & Resorts",
    "Thalassa Sousse Resort & Aquapark",
    "Hasdrubal Thalassa & Spa",
    "Iberostar Kuriat Palace Monastir",
    "Radisson Blu Resort & Thalasso",
    "Mövenpick Resort & Marine Spa",
    "Royal Thalassa Monastir",
    "Hôtel Les Oliviers Palace Sfax"
  ];

  // Generate image lists based on extracted normalized files
  const getLogos = () => {
    switch (activeTab) {
      case 'hotels':
        return Array.from({ length: 51 }, (_, i) => ({
          src: `/logos/hotel_logo_${i + 1}.jpeg`,
          alt: `Hôtel Référence EcoPower ${i + 1}`
        }));
      case 'cliniques':
        return Array.from({ length: 7 }, (_, i) => ({
          src: `/logos/clinique_logo_${i + 1}.jpeg`,
          alt: `Clinique Partenaire EcoPower ${i + 1}`
        }));
      case 'universites':
        return Array.from({ length: 5 }, (_, i) => ({
          src: `/logos/universite_logo_${i + 1}.jpeg`,
          alt: `Université / Foyer Partenaire ${i + 1}`
        }));
      case 'entreprises':
      default:
        return Array.from({ length: 13 }, (_, i) => ({
          src: `/logos/partenaire_logo_${i + 1}.${i === 12 ? 'png' : 'jpeg'}`,
          alt: `Entreprise Partenaire ${i + 1}`
        }));
    }
  };

  const logos = getLogos();

  return (
    <section className="py-16 bg-slate-50 border-y border-slate-200 overflow-hidden" id="references-section">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 mb-10">
        
        {/* Section Header */}
        <div className="text-center max-w-3xl mx-auto">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-brand-100 text-brand-800 text-xs font-bold uppercase tracking-wider mb-3">
            <Award className="w-4 h-4 text-brand-600" />
            <span>{language === 'ar' ? 'ثقة المؤسسات الرائدة' : 'Reconnu par les plus grands établissements'}</span>
          </div>
          <h2 className="text-3xl sm:text-4xl font-extrabold text-slate-900 tracking-tight font-serif">
            {language === 'ar' ? 'مراجعنا في تونس منذ أكثر من 10 سنوات' : 'Nos Références & Partenaires en Tunisie'}
          </h2>
          <p className="mt-3 text-slate-600 text-base sm:text-lg">
            {language === 'ar' 
              ? 'تعتمد أكثر من 100 مؤسسة فندقية وصحية في تونس على تكنولوجيا إيكوباور لتخفيض فواتير استهلاك الماء والغاز مع مطابقة معايير ISO الدولية.'
              : 'Plus de 100 hôtels, 60% des cliniques de Tunisie, des universités et des fleurons industriels nous font confiance pour rentabiliser leur consommation.'}
          </p>
        </div>

        {/* Category Tabs */}
        <div className="flex flex-wrap items-center justify-center gap-2 sm:gap-3 mt-8">
          {categories.map((cat) => {
            const Icon = cat.icon;
            const isActive = activeTab === cat.id;
            return (
              <button
                key={cat.id}
                onClick={() => setActiveTab(cat.id)}
                className={`flex items-center gap-2 px-4 py-2.5 rounded-xl font-bold text-sm transition-all shadow-xs ${
                  isActive
                    ? 'bg-brand-700 text-white shadow-md shadow-brand-700/20 scale-105'
                    : 'bg-white text-slate-600 hover:bg-slate-100 border border-slate-200'
                }`}
              >
                <Icon className={`w-4 h-4 ${isActive ? 'text-emerald-300' : 'text-slate-400'}`} />
                <span>{cat.label}</span>
              </button>
            );
          })}
        </div>

        {/* Highlights Banner according to active tab */}
        {activeTab === 'cliniques' && (
          <div className="mt-6 p-4 bg-emerald-50 rounded-2xl border border-emerald-200/80 max-w-4xl mx-auto flex flex-wrap items-center justify-center gap-3 text-xs sm:text-sm font-semibold text-emerald-900">
            <span className="font-bold text-emerald-800 flex items-center gap-1">
              <CheckCircle2 className="w-4 h-4 text-emerald-600" /> Cliniques Référentes :
            </span>
            {clinicNames.map((name, idx) => (
              <span key={idx} className="bg-white px-2.5 py-1 rounded-md shadow-2xs border border-emerald-100">
                {name}
              </span>
            ))}
          </div>
        )}

        {activeTab === 'hotels' && (
          <div className="mt-6 p-4 bg-skywater-50 rounded-2xl border border-skywater-200/80 max-w-4xl mx-auto flex flex-wrap items-center justify-center gap-2.5 text-xs sm:text-sm font-semibold text-skywater-900">
            <span className="font-bold text-skywater-800 flex items-center gap-1">
              <CheckCircle2 className="w-4 h-4 text-skywater-600" /> Parmi les chaînes équipées :
            </span>
            {hotelHighlights.map((name, idx) => (
              <span key={idx} className="bg-white px-2.5 py-1 rounded-md shadow-2xs border border-skywater-100">
                {name}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Infinite Scrolling Logos Track */}
      <div className="relative w-full overflow-hidden py-4 bg-white/70 backdrop-blur-xs border-y border-slate-200/60">
        <div className="animate-marquee flex items-center gap-6 sm:gap-8 px-4">
          {[...logos, ...logos, ...logos].map((logo, index) => (
            <div
              key={index}
              className="flex-shrink-0 w-36 h-24 sm:w-44 sm:h-28 bg-white rounded-2xl border border-slate-200/80 p-3 shadow-xs hover:shadow-md transition-all flex items-center justify-center group overflow-hidden"
            >
              <img
                src={logo.src}
                alt={logo.alt}
                onError={(e) => {
                  // Fallback if image doesn't load
                  e.target.style.display = 'none';
                  e.target.parentNode.innerHTML = `<div class="text-xs text-center font-bold text-slate-500">Partenaire EcoPower</div>`;
                }}
                className="max-h-full max-w-full object-contain filter grayscale group-hover:grayscale-0 group-hover:scale-105 transition-all duration-300"
                loading="lazy"
              />
            </div>
          ))}
        </div>
      </div>

      {/* Trust stats below carousel */}
      <div className="max-w-6xl mx-auto px-4 mt-12 grid grid-cols-2 sm:grid-cols-4 gap-4 text-center">
        <div className="bg-white p-5 rounded-2xl border border-slate-200/70 shadow-xs">
          <div className="text-3xl font-black text-brand-700">60%</div>
          <div className="text-xs font-semibold text-slate-600 mt-1">D'économie d'eau mesurée</div>
        </div>
        <div className="bg-white p-5 rounded-2xl border border-slate-200/70 shadow-xs">
          <div className="text-3xl font-black text-brand-700">&lt; 90j</div>
          <div className="text-xs font-semibold text-slate-600 mt-1">Retour sur investissement pro</div>
        </div>
        <div className="bg-white p-5 rounded-2xl border border-slate-200/70 shadow-xs">
          <div className="text-3xl font-black text-brand-700">3 Ans</div>
          <div className="text-xs font-semibold text-slate-600 mt-1">Garantie constructeur Hostaform</div>
        </div>
        <div className="bg-white p-5 rounded-2xl border border-slate-200/70 shadow-xs">
          <div className="text-3xl font-black text-brand-700">+10 Ans</div>
          <div className="text-xs font-semibold text-slate-600 mt-1">D'expertise terrain en Tunisie</div>
        </div>
      </div>
    </section>
  );
};
