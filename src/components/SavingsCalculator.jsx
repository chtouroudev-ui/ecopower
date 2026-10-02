import React, { useState } from 'react';
import { Calculator, ArrowRight, Droplets, Flame, TrendingDown, CheckCircle2, Sparkles } from 'lucide-react';
import { useCart } from '../context/CartContext';

export const SavingsCalculator = ({ onSelectPack }) => {
  const { language, addToCart } = useCart();
  const [profile, setProfile] = useState('residentiel'); // residentiel | pro
  
  // Residentiel sliders
  const [familySize, setFamilySize] = useState(4);
  const [currentSonede, setCurrentSonede] = useState(85); // DT par facture trimestrielle
  const [currentStegGas, setCurrentStegGas] = useState(65); // DT par facture de gaz

  // Pro sliders
  const [roomCount, setRoomCount] = useState(60);
  const [monthlyWaterPro, setMonthlyWaterPro] = useState(4500); // DT / mois

  // Math Calculations (Residentiel)
  // Water savings: ~55% reduction
  // Gas savings for hot water heating: ~30%
  const annualWaterSavingsDt = Math.round(currentSonede * 4 * 0.52);
  const annualGasSavingsDt = Math.round(currentStegGas * 6 * 0.32);
  const totalAnnualSavingsDt = annualWaterSavingsDt + annualGasSavingsDt;
  const litresSavedYear = Math.round(familySize * 135 * 30 * 12 * 0.55); // ~135L/pers/day

  // Math Calculations (Pro)
  // ROI < 90 days
  const annualSavingsPro = Math.round(monthlyWaterPro * 12 * 0.48);
  const estimatedInvestmentPro = Math.round(roomCount * 45);
  const roiDays = Math.max(30, Math.round((estimatedInvestmentPro / (annualSavingsPro / 365))));

  return (
    <div className="bg-white rounded-3xl border border-slate-200/90 shadow-xl shadow-slate-200/50 p-6 sm:p-10 max-w-4xl mx-auto my-10">
      
      {/* Header */}
      <div className="text-center max-w-2xl mx-auto mb-8">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-skywater-100 text-skywater-800 text-xs font-bold uppercase tracking-wider mb-2">
          <Calculator className="w-4 h-4 text-skywater-600" />
          <span>{language === 'ar' ? 'حساب دقيق بالدينار التونسي' : 'Simulateur d’Amortissement Réel'}</span>
        </div>
        <h3 className="text-2xl sm:text-3xl font-extrabold text-slate-900 font-serif">
          {language === 'ar' 
            ? 'احسب شكون قداش تنجم توفر مع إيكوباور' 
            : 'Estimez vos Économies Immédiates en Tunisie'}
        </h3>
        <p className="text-slate-600 text-sm mt-2">
          {language === 'ar'
            ? 'حساب تقديري مبني على أسعار سوناد (SONEDE) والستاغ (STEG) وتجارب حرفائنا'
            : 'Basé sur les tranches progressives de la SONEDE et la consommation de gaz STEG.'}
        </p>

        {/* Profile Switcher */}
        <div className="inline-flex p-1 bg-slate-100 rounded-2xl mt-5 border border-slate-200">
          <button
            onClick={() => setProfile('residentiel')}
            className={`px-5 py-2 rounded-xl text-xs sm:text-sm font-bold transition-all ${
              profile === 'residentiel'
                ? 'bg-white text-brand-800 shadow-xs'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            🏡 Particuliers (Maison / Appartement)
          </button>
          <button
            onClick={() => setProfile('pro')}
            className={`px-5 py-2 rounded-xl text-xs sm:text-sm font-bold transition-all ${
              profile === 'pro'
                ? 'bg-white text-brand-800 shadow-xs'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            🏢 Professionnels (Hôtel / Clinique)
          </button>
        </div>
      </div>

      {profile === 'residentiel' ? (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-center">
          
          {/* Sliders Input */}
          <div className="lg:col-span-7 space-y-6">
            
            {/* Slider 1: Family size */}
            <div>
              <div className="flex justify-between items-center mb-2">
                <label className="text-sm font-bold text-slate-700">
                  Nombre de personnes au foyer :
                </label>
                <span className="px-3 py-1 bg-brand-50 text-brand-700 rounded-lg text-sm font-black">
                  {familySize} {familySize > 1 ? 'personnes' : 'personne'}
                </span>
              </div>
              <input
                type="range"
                min="1"
                max="8"
                step="1"
                value={familySize}
                onChange={(e) => setFamilySize(parseInt(e.target.value))}
                className="w-full h-2.5 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-brand-600"
              />
              <div className="flex justify-between text-[11px] text-slate-600 mt-1">
                <span>1 pers.</span>
                <span>4 pers.</span>
                <span>8+ pers.</span>
              </div>
            </div>

            {/* Slider 2: Facture SONEDE */}
            <div>
              <div className="flex justify-between items-center mb-2">
                <label className="text-sm font-bold text-slate-700 flex items-center gap-1.5">
                  <Droplets className="w-4 h-4 text-skywater-500" />
                  Facture trimestrielle SONEDE moyenne :
                </label>
                <span className="px-3 py-1 bg-skywater-50 text-skywater-700 rounded-lg text-sm font-black">
                  {currentSonede} DT
                </span>
              </div>
              <input
                type="range"
                min="30"
                max="300"
                step="5"
                value={currentSonede}
                onChange={(e) => setCurrentSonede(parseInt(e.target.value))}
                className="w-full h-2.5 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-skywater-500"
              />
              <div className="flex justify-between text-[11px] text-slate-600 mt-1">
                <span>30 DT</span>
                <span>150 DT</span>
                <span>300 DT</span>
              </div>
            </div>

            {/* Slider 3: Facture Gaz STEG */}
            <div>
              <div className="flex justify-between items-center mb-2">
                <label className="text-sm font-bold text-slate-700 flex items-center gap-1.5">
                  <Flame className="w-4 h-4 text-energy-500" />
                  Facture de gaz STEG (chauffage eau chaude) :
                </label>
                <span className="px-3 py-1 bg-amber-50 text-amber-700 rounded-lg text-sm font-black">
                  {currentStegGas} DT
                </span>
              </div>
              <input
                type="range"
                min="20"
                max="250"
                step="5"
                value={currentStegGas}
                onChange={(e) => setCurrentStegGas(parseInt(e.target.value))}
                className="w-full h-2.5 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-energy-500"
              />
              <div className="flex justify-between text-[11px] text-slate-600 mt-1">
                <span>20 DT</span>
                <span>120 DT</span>
                <span>250 DT</span>
              </div>
            </div>

            <div className="p-3 bg-slate-50 rounded-xl text-xs text-slate-500 flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0" />
              <span>Double effet : Moins de volume d'eau = Rétrogradation automatique vers une tranche tarifaire SONEDE moins chère.</span>
            </div>
          </div>

          {/* Results Card */}
          <div className="lg:col-span-5 bg-gradient-to-br from-brand-900 to-brand-800 text-white rounded-2xl p-6 shadow-xl relative overflow-hidden flex flex-col justify-between">
            <div className="absolute -right-10 -bottom-10 w-40 h-40 bg-skywater-500/20 rounded-full blur-2xl pointer-events-none"></div>

            <div>
              <div className="text-xs uppercase tracking-wider text-emerald-300 font-bold mb-1 flex items-center gap-1">
                <Sparkles className="w-3.5 h-3.5" /> Économie Annuelle Totale Estimée
              </div>
              <div className="text-4xl sm:text-5xl font-black text-white tracking-tight">
                {totalAnnualSavingsDt} <span className="text-xl font-bold text-emerald-400">DT / an</span>
              </div>
              <p className="text-xs text-slate-300 mt-1">
                Soit environ <strong>{Math.round(totalAnnualSavingsDt / 12)} DT</strong> de pouvoir d'achat récupéré chaque mois !
              </p>
            </div>

            <div className="my-6 space-y-3 border-y border-white/10 py-4 text-xs">
              <div className="flex justify-between items-center">
                <span className="text-slate-300 flex items-center gap-1.5">
                  <Droplets className="w-3.5 h-3.5 text-skywater-400" /> Économie Eau (SONEDE) :
                </span>
                <span className="font-bold text-white text-sm">{annualWaterSavingsDt} DT/an</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-slate-300 flex items-center gap-1.5">
                  <Flame className="w-3.5 h-3.5 text-energy-400" /> Économie Gaz (STEG) :
                </span>
                <span className="font-bold text-white text-sm">{annualGasSavingsDt} DT/an</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-slate-300 flex items-center gap-1.5">
                  <TrendingDown className="w-3.5 h-3.5 text-emerald-400" /> Eau préservée :
                </span>
                <span className="font-bold text-emerald-300 text-sm">~{litresSavedYear.toLocaleString()} Litres</span>
              </div>
            </div>

            <div>
              <div className="text-[11px] text-slate-300 mb-2">
                Pack Recommandé : {familySize <= 3 ? 'Pack Appartement (66 DT)' : 'Pack Maison / Villa (109 DT)'}
              </div>
              <button
                onClick={() => {
                  if (onSelectPack) {
                    onSelectPack(familySize <= 3 ? 'pack-appartement-4l' : 'pack-maison-4l');
                  }
                }}
                className="w-full bg-gradient-to-r from-energy-500 to-energy-600 hover:from-energy-600 hover:to-energy-500 text-white py-3 px-4 rounded-xl font-bold text-sm flex items-center justify-center gap-2 shadow-lg shadow-energy-500/30 transition-all hover:scale-[1.02]"
              >
                <span>Commander ce Pack</span>
                <ArrowRight className="w-4 h-4" />
              </button>
            </div>

          </div>
        </div>
      ) : (
        /* PRO SIMULATOR */
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-center">
          <div className="lg:col-span-7 space-y-6">
            <div>
              <div className="flex justify-between items-center mb-2">
                <label className="text-sm font-bold text-slate-700">
                  Capacité (Nombre de chambres / lits / sanitaires) :
                </label>
                <span className="px-3 py-1 bg-brand-50 text-brand-700 rounded-lg text-sm font-black">
                  {roomCount} unités
                </span>
              </div>
              <input
                type="range"
                min="10"
                max="350"
                step="10"
                value={roomCount}
                onChange={(e) => setRoomCount(parseInt(e.target.value))}
                className="w-full h-2.5 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-brand-600"
              />
            </div>

            <div>
              <div className="flex justify-between items-center mb-2">
                <label className="text-sm font-bold text-slate-700">
                  Facture d'eau mensuelle actuelle de l'établissement :
                </label>
                <span className="px-3 py-1 bg-skywater-50 text-skywater-700 rounded-lg text-sm font-black">
                  {monthlyWaterPro.toLocaleString()} DT / mois
                </span>
              </div>
              <input
                type="range"
                min="1000"
                max="25000"
                step="500"
                value={monthlyWaterPro}
                onChange={(e) => setMonthlyWaterPro(parseInt(e.target.value))}
                className="w-full h-2.5 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-skywater-500"
              />
            </div>

            <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-2xl text-xs text-emerald-900 space-y-1">
              <div className="font-bold text-emerald-950 flex items-center gap-1.5">
                <CheckCircle2 className="w-4 h-4 text-emerald-600" /> Diagnostic d'amortissement gratuit par notre bureau d'études
              </div>
              <p>Nous réalisons gratuitement un test de débit et un état des lieux point par point de votre hôtel ou clinique.</p>
            </div>
          </div>

          <div className="lg:col-span-5 bg-gradient-to-br from-brand-900 to-slate-900 text-white rounded-2xl p-6 shadow-xl flex flex-col justify-between">
            <div>
              <div className="text-xs uppercase tracking-wider text-emerald-300 font-bold mb-1">
                Gains Annuels Établissement
              </div>
              <div className="text-4xl sm:text-5xl font-black text-white tracking-tight">
                {annualSavingsPro.toLocaleString()} <span className="text-xl font-bold text-emerald-400">DT</span>
              </div>
              <p className="text-xs text-slate-300 mt-1">
                Retour sur investissement estimé en moins de <strong>{roiDays} jours</strong> !
              </p>
            </div>

            <div className="my-6 space-y-2 border-y border-white/10 py-4 text-xs">
              <div className="flex justify-between">
                <span className="text-slate-300">Normes sanitaires :</span>
                <span className="font-bold text-emerald-300">Certifié ACS & ISO</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-300">Garantie matériel :</span>
                <span className="font-bold text-white">3 Ans Delrin / Hostaform</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-300">Pose & test de débit :</span>
                <span className="font-bold text-white">Offerts par nos techniciens</span>
              </div>
            </div>

            <a
              href="#devis-pro"
              className="w-full bg-brand-500 hover:bg-brand-600 text-white py-3 px-4 rounded-xl font-bold text-sm flex items-center justify-center gap-2 shadow-lg transition-all"
            >
              <span>Demander un Audit & Devis Gratuit</span>
              <ArrowRight className="w-4 h-4" />
            </a>
          </div>
        </div>
      )}

    </div>
  );
};
