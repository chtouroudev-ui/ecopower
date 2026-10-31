import React, { useState, useMemo } from 'react';
import { Building2, Hotel, Hospital, GraduationCap, Award, CheckCircle2 } from 'lucide-react';
import { useCart } from '../context/CartContext';

// Logos certifiés en couleurs réelles éclatantes (zéro logo noir / monochrome ou terne)
const CLINIQUE_LOGOS = [
  'clinique_logo_1.jpeg',
  'clinique_logo_2.jpeg',
  'clinique_logo_3.jpeg',
  'clinique_logo_4.jpeg',
  'clinique_logo_5.jpeg',
  'clinique_logo_6.png',
  'clinique_logo_7.jpeg',
];

const HOTEL_LOGOS = [
  'hotel_logo_1.jpeg',
  'hotel_logo_3.jpeg',
  'hotel_logo_4.jpeg',
  'hotel_logo_5.jpeg',
  'hotel_logo_6.png',
  'hotel_logo_7.png',
  'hotel_logo_8.jpeg',
  'hotel_logo_10.jpeg',
  'hotel_logo_11.jpeg',
  'hotel_logo_12.jpeg',
  'hotel_logo_13.jpeg',
  'hotel_logo_14.png',
  'hotel_logo_15.png',
  'hotel_logo_17.jpeg',
  'hotel_logo_18.jpeg',
  'hotel_logo_20.png',
  'hotel_logo_21.jpeg',
  'hotel_logo_22.jpeg',
  'hotel_logo_23.png',
  'hotel_logo_25.png',
  'hotel_logo_26.jpeg',
  'hotel_logo_28.jpeg',
  'hotel_logo_29.jpeg',
  'hotel_logo_34.png',
  'hotel_logo_35.png',
  'hotel_logo_36.png',
  'hotel_logo_37.png',
  'hotel_logo_38.png',
  'hotel_logo_39.jpeg',
  'hotel_logo_40.png',
  'hotel_logo_41.png',
  'hotel_logo_43.jpeg',
  'hotel_logo_44.png',
  'hotel_logo_48.png',
  'hotel_logo_49.jpeg',
  'hotel_logo_50.png',
];

const ENTREPRISE_LOGOS = [
  'partenaire_logo_1.jpeg',
  'partenaire_logo_2.png',
  'partenaire_logo_3.png',
  'partenaire_logo_4.png',
  'partenaire_logo_5.png',
  'partenaire_logo_8.jpeg',
  'partenaire_logo_9.jpeg',
  'partenaire_logo_10.jpeg',
  'partenaire_logo_11.jpeg',
  'partenaire_logo_12.jpeg',
  'partenaire_logo_13.png',
];

const UNIVERSITE_LOGOS = [
  'universite_logo_3.png',
  'universite_logo_4.jpeg',
  'universite_logo_5.png',
];

export const ReferencesCarousel = () => {
  const { language } = useCart();
  const [activeTab, setActiveTab] = useState('hotels');

  const categories = [
    { id: 'hotels', label: language === 'ar' ? 'أكثر من 100 نزل' : '+100 Hôtels en Tunisie', icon: Hotel, count: HOTEL_LOGOS.length },
    { id: 'cliniques', label: language === 'ar' ? '+60% من المصحّات' : '+60% des Cliniques', icon: Hospital, count: CLINIQUE_LOGOS.length },
    { id: 'entreprises', label: language === 'ar' ? 'شركات وبنوك' : 'Banques & Entreprises', icon: Building2, count: ENTREPRISE_LOGOS.length },
    { id: 'universites', label: language === 'ar' ? 'جامعات ومبيتات' : 'Universités & Foyers', icon: GraduationCap, count: UNIVERSITE_LOGOS.length },
  ];

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

  const logos = useMemo(() => {
    let files = HOTEL_LOGOS;
    if (activeTab === 'cliniques') {
      files = CLINIQUE_LOGOS;
    } else if (activeTab === 'universites') {
      files = UNIVERSITE_LOGOS;
    } else if (activeTab === 'entreprises') {
      files = ENTREPRISE_LOGOS;
    }

    return files.map((fileName) => ({
      src: `/logos/${fileName}`,
      alt: ''
    }));
  }, [activeTab]);

  return (
    <section className="py-14 sm:py-16 bg-slate-50 border-y border-slate-200 overflow-hidden" id="references-section">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 mb-8">
        
        {/* Section Header */}
        <div className="text-center max-w-3xl mx-auto">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-blue-100 text-blue-800 text-xs font-bold uppercase tracking-wider mb-2.5">
            <Award className="w-4 h-4 text-blue-600" />
            <span>{language === 'ar' ? 'أكبر المؤسسات يثقو فينا' : 'Reconnu par les plus grands établissements'}</span>
          </div>
          <h2 className="text-2xl sm:text-4xl font-extrabold text-slate-900 tracking-tight font-serif">
            {language === 'ar' ? 'مراجعنا وشركاؤنا في تونس' : 'Nos Références & Partenaires en Tunisie'}
          </h2>
          <p className="mt-2 text-slate-600 text-sm sm:text-base leading-relaxed">
            {language === 'ar' 
              ? 'أكثر من 100 نزل، 60% من المصحّات في تونس، جامعات وشركات كبار يثقو فينا باش ينقّصو في استهلاكهم.'
              : 'Plus de 100 hôtels, 60% des cliniques de Tunisie, des universités et des fleurons industriels nous font confiance pour rentabiliser leur consommation.'}
          </p>
        </div>

        {/* Category Tabs */}
        <div className="flex flex-wrap items-center justify-center gap-2 sm:gap-3 mt-6 sm:mt-8">
          {categories.map((cat) => {
            const Icon = cat.icon;
            const isActive = activeTab === cat.id;
            return (
              <button
                key={cat.id}
                onClick={() => setActiveTab(cat.id)}
                className={`flex items-center gap-2 px-3.5 py-2 sm:px-4 sm:py-2.5 rounded-xl font-bold text-xs sm:text-sm transition-all shadow-xs ${
                  isActive
                    ? 'bg-blue-700 text-white shadow-md shadow-blue-700/20 scale-105'
                    : 'bg-white text-slate-600 hover:bg-slate-100 border border-slate-200'
                }`}
              >
                <Icon className={`w-4 h-4 ${isActive ? 'text-sky-300' : 'text-slate-400'}`} />
                <span>{cat.label}</span>
              </button>
            );
          })}
        </div>

        {/* Highlights Banner */}
        {activeTab === 'cliniques' && (
          <div className="mt-6 p-4 bg-blue-50 rounded-2xl border border-blue-200/80 max-w-4xl mx-auto flex flex-wrap items-center justify-center gap-2.5 text-xs sm:text-sm font-semibold text-blue-900 animate-in fade-in">
            <span className="font-bold text-blue-800 flex items-center gap-1">
              <CheckCircle2 className="w-4 h-4 text-blue-600" /> {language === 'ar' ? 'مصحّات من مراجعنا:' : 'Cliniques Référentes :'}
            </span>
            {clinicNames.map((name, idx) => (
              <span key={idx} className="bg-white px-2.5 py-1 rounded-md shadow-xs border border-blue-100 text-slate-800 font-medium">
                {name}
              </span>
            ))}
          </div>
        )}

        {activeTab === 'hotels' && (
          <div className="mt-6 p-4 bg-sky-50 rounded-2xl border border-sky-200/80 max-w-4xl mx-auto flex flex-wrap items-center justify-center gap-2.5 text-xs sm:text-sm font-semibold text-sky-900 animate-in fade-in">
            <span className="font-bold text-sky-800 flex items-center gap-1">
              <CheckCircle2 className="w-4 h-4 text-sky-600" /> {language === 'ar' ? 'من السلاسل المجهّزة:' : 'Parmi les chaînes équipées :'}
            </span>
            {hotelHighlights.map((name, idx) => (
              <span key={idx} className="bg-white px-2.5 py-1 rounded-md shadow-xs border border-sky-100 text-slate-800 font-medium">
                {name}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Infinite Scrolling Logos Track — 100% REAL VIBRANT COLORS ONLY */}
      <div className="relative w-full overflow-hidden py-4 bg-white/95 border-y border-slate-200 shadow-inner">
        <div className="animate-marquee flex items-center gap-5 sm:gap-6 px-4">
          {[...logos, ...logos].map((logo, index) => (
            <div
              key={index}
              className="logo-card shrink-0 w-36 h-24 sm:w-44 sm:h-28 bg-white rounded-2xl border border-slate-200 p-3 shadow-xs hover:shadow-md transition-all flex items-center justify-center group overflow-hidden"
            >
              <img
                src={logo.src}
                alt=""
                loading="eager"
                onError={(e) => {
                  e.currentTarget.closest('.logo-card')?.remove();
                }}
                className="max-h-full max-w-full object-contain group-hover:scale-105 transition-transform duration-300"
              />
            </div>
          ))}
        </div>
      </div>

      {/* Trust stats below carousel */}
      <div className="max-w-6xl mx-auto px-4 mt-10 grid grid-cols-2 sm:grid-cols-4 gap-3 sm:gap-4 text-center">
        <div className="bg-white p-4 sm:p-5 rounded-2xl border border-slate-200 shadow-xs">
          <div className="text-2xl sm:text-3xl font-black text-blue-700">60%</div>
          <div className="text-xs font-semibold text-slate-600 mt-1">{language === 'ar' ? 'توفير في الماء مقيوس' : "D'économie d'eau mesurée"}</div>
        </div>
        <div className="bg-white p-4 sm:p-5 rounded-2xl border border-slate-200 shadow-xs">
          <div className="text-2xl sm:text-3xl font-black text-blue-700">{language === 'ar' ? 'أقل من 90 يوم' : '< 90j'}</div>
          <div className="text-xs font-semibold text-slate-600 mt-1">{language === 'ar' ? 'ترجيع الفلوس للمحترفين' : 'Retour sur investissement pro'}</div>
        </div>
        <div className="bg-white p-4 sm:p-5 rounded-2xl border border-slate-200 shadow-xs">
          <div className="text-2xl sm:text-3xl font-black text-blue-700">{language === 'ar' ? '3 سنين' : '3 Ans'}</div>
          <div className="text-xs font-semibold text-slate-600 mt-1">{language === 'ar' ? 'ضمان المصنّع Hostaform' : 'Garantie constructeur Hostaform'}</div>
        </div>
        <div className="bg-white p-4 sm:p-5 rounded-2xl border border-slate-200 shadow-xs">
          <div className="text-2xl sm:text-3xl font-black text-blue-700">{language === 'ar' ? 'أكثر من 10 سنين' : '+10 Ans'}</div>
          <div className="text-xs font-semibold text-slate-600 mt-1">{language === 'ar' ? 'خبرة على الميدان في تونس' : "D'expertise terrain en Tunisie"}</div>
        </div>
      </div>
    </section>
  );
};
