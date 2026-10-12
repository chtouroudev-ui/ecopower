import React from 'react';
import { useCart } from '../context/CartContext';
import { SavingsCalculator } from '../components/SavingsCalculator';
import { FaucetComparison } from '../components/FaucetComparison';
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

// Textes de la page Particuliers : français et darija tunisienne
const TXT = {
  fr: {
    cur: 'DT',
    heroBadge: 'Espace Particuliers & Foyers',
    heroTitle: 'Rajoutez du Pouvoir d’Achat à Votre Famille',
    heroText: "En économisant l'eau (SONEDE) et son chauffage au gaz (STEG). Découvrez pourquoi plus de 80% des foyers tunisiens surconsomment inutilement et comment y remédier en 2 minutes.",
    problemBadge: 'Le problème méconnu de la pression en Tunisie',
    problemTitle: 'Pourquoi payez-vous le double sur vos factures d’eau et de gaz ?',
    problem1: ["En Europe, la pression d'eau est normalisée à ", '3 Bars', ', délivrant en moyenne 12 litres/min pour un robinet et 16 litres/min pour une douche.'],
    problem2: ['En Tunisie, la pression de base SONEDE n’est pas normalisée.', " Cela engendre pour plus de 80% des utilisateurs une surconsommation d'eau pouvant atteindre ", 'le double par minute', ' (20 à 24 litres/min !).'],
    problem3: ['Cette surconsommation mécanique entraîne immédiatement une surconsommation de ', 'Gaz (STEG)', " pour le chauffage de l'eau, ainsi qu’un passage dans les ", 'tranches tarifaires SONEDE supérieures', ' beaucoup plus onéreuses.'],
    checks: ['Régulation à 4 ou 5 L/min robinets', 'Régulation à 5 ou 7 L/min douches', 'Garantie 3 ans Hostaform'],
    giftKicker: 'Cadeau Exclusif EcoPower',
    giftTitle: 'Sac Débit-Mètre Offert',
    giftText: ['Un sac débit-mètre gradué vous sera livré ', 'gratuitement', " avec chaque Pack Appartement ou Maison. Il vous permet de mesurer votre consommation en 10 secondes sous votre robinet avant et après l'installation !"],
    giftFooter: 'Testez et constatez vos économies en direct chez vous !',
    packsTitle: 'Les Packs Ecopower pour Particuliers',
    packsText: "Prêts à l'emploi • Se vissent à la main sans outils • Garantie 3 ans • Écosac garanti à vie",
    composition: 'Composition du pack :',
    addPack: (price) => `Ajouter ce Pack au Panier (${price} DT)`,
    unitTitle: 'Vous préférez acheter vos régulateurs ou accessoires à l’unité ?',
    unitText: 'Retrouvez nos bagues inox, nos cartouches hydro-économes de 2L à 5L/min, nos pommes de douche massantes et nos ampoules LED à détection dans notre boutique complète.',
    unitCta: 'Accéder à la Boutique au Détail',
    packs: {
      'pack-appartement-4l': {
        name: 'Pack Appartement 4 Litres',
        idealFor: 'Appartement S+1, S+2 ou S+3 (1 Salle de Bain)',
        composition: [
          '2x Hydro-économes 4L/min pour robinets (cuisine + lavabo)',
          '1x Régulateur Inox 5L/min pour flexible de douche',
          '1x Eco-Sac WC 3 Litres imputrescible (garanti à vie)',
          '1x Sac Débit-Mètre gradué offert gratuitement'
        ]
      },
      'pack-appartement-5l': {
        name: 'Pack Appartement 5 Litres',
        idealFor: 'Appartement recherchant un débit plus abondant',
        composition: [
          '2x Hydro-économes 5L/min pour robinets',
          '1x Régulateur Inox 7L/min pour flexible de douche',
          '1x Eco-Sac WC 3 Litres imputrescible (garanti à vie)',
          '1x Sac Débit-Mètre gradué offert gratuitement'
        ]
      },
      'pack-maison-4l': {
        name: 'Pack Maison / Villa 4 Litres',
        idealFor: 'Villa, Étage de villa ou Maison avec 2 salles de bain',
        composition: [
          '4x Hydro-économes 4L/min pour robinets',
          '2x Régulateurs Inox pour douches et sanitaires',
          '2x Eco-Sacs WC 3 Litres imputrescibles (garantis à vie)',
          '1x Sac Débit-Mètre gradué offert gratuitement'
        ]
      },
      'pack-maison-5l': {
        name: 'Pack Maison / Villa 5 Litres',
        idealFor: 'Grande famille / Villa avec fort besoin d’utilisation',
        composition: [
          '4x Hydro-économes 5L/min pour robinets',
          '2x Régulateurs Inox pour douches 7L/min',
          '2x Eco-Sacs WC 3 Litres imputrescibles (garantis à vie)',
          '1x Sac Débit-Mètre gradué offert gratuitement'
        ]
      }
    }
  },
  ar: {
    cur: 'د.ت',
    heroBadge: 'فضاء العايلات والديار',
    heroTitle: 'زيد في القدرة الشرائية متاع عايلتك',
    heroText: 'وفّر في الماء (الصوناد) وفي الغاز اللي يسخّنو (الستاغ). اكتشف علاش أكثر من 80% من الديار في تونس يستهلكو أكثر من اللازم بلا فايدة، وكيفاش تصلّح هالمشكل في دقيقتين.',
    problemBadge: 'مشكل الضغط في تونس اللي برشا ما يعرفوهش',
    problemTitle: 'علاش تخلّص الضعف في فاتورة الماء والغاز؟',
    problem1: ['في أوروبا، ضغط الماء مظبوط على ', '3 بار', '، يعطي في المعدّل 12 لتر في الدقيقة للروبيني و16 لتر في الدقيقة للدوش.'],
    problem2: ['في تونس، ضغط الصوناد موش مظبوط.', ' وهذا يخلّي أكثر من 80% من الناس يستهلكو ماء زايد ينجم يوصل لـ ', 'الضعف في الدقيقة', ' (20 لـ 24 لتر في الدقيقة!).'],
    problem3: ['الاستهلاك الزايد هذا يجيب معاه طول استهلاك زايد في ', 'الغاز (الستاغ)', ' باش تسخّن الماء، ويطلّعك لـ ', 'شرائح الصوناد الغالية', ' اللي سومها أكثر بالبرشا.'],
    checks: ['ظبط الروبينيات على 4 ولا 5 L/min', 'ظبط الدوش على 5 ولا 7 L/min', 'ضمان 3 سنين Hostaform'],
    giftKicker: 'هدية حصرية من EcoPower',
    giftTitle: 'كيس قيس الصبيب هدية',
    giftText: ['كيس مدرّج لقيس الصبيب يوصلك ', 'بلاش', ' مع كل باك شقة ولا دار. بيه تقيس قدّاش تستهلك في 10 ثواني تحت الروبيني، قبل التركيب وبعدو!'],
    giftFooter: 'جرّب وشوف التوفير بعينيك في دارك!',
    packsTitle: 'باكات EcoPower للعايلات',
    packsText: 'جاهزين للاستعمال • يتسكّرو باليد بلا عدّة • ضمان 3 سنين • الإيكو-ساك مضمون مدى الحياة',
    composition: 'شنوّة فيه الباك:',
    addPack: (price) => `زيد الباك هذا للسلة (${price} د.ت)`,
    unitTitle: 'تحب تشري المنظّمات ولا الأكسسوارات بالواحد؟',
    unitText: 'تلقى الحلقات الإينوكس، الخراطيش الموفّرة من 2L لـ 5L/min، رؤوس الدوش اللي تعمل ماساج، ولمبات LED بالكابتور في المتجر متاعنا.',
    unitCta: 'ادخل للمتجر',
    packs: {
      'pack-appartement-4l': {
        name: 'باك الشقة 4 لتر',
        idealFor: 'شقة S+1، S+2 ولا S+3 (بيت بانو وحدة)',
        composition: [
          '2x موفّرات 4L/min للروبينيات (الكوجينة + اللافابو)',
          '1x منظّم إينوكس 5L/min لفليكسيبل الدوش',
          '1x إيكو-ساك للتواليت 3 لتر ما يتحلّش (مضمون مدى الحياة)',
          '1x كيس مدرّج لقيس الصبيب هدية'
        ]
      },
      'pack-appartement-5l': {
        name: 'باك الشقة 5 لتر',
        idealFor: 'للشقة اللي تحب صبيب أقوى شوية',
        composition: [
          '2x موفّرات 5L/min للروبينيات',
          '1x منظّم إينوكس 7L/min لفليكسيبل الدوش',
          '1x إيكو-ساك للتواليت 3 لتر ما يتحلّش (مضمون مدى الحياة)',
          '1x كيس مدرّج لقيس الصبيب هدية'
        ]
      },
      'pack-maison-4l': {
        name: 'باك الدار / الفيلا 4 لتر',
        idealFor: 'فيلا، طابق فيلا ولا دار فيها زوز بيوت بانو',
        composition: [
          '4x موفّرات 4L/min للروبينيات',
          '2x منظّمات إينوكس للدوش والتواليت',
          '2x إيكو-ساك للتواليت 3 لتر ما يتحلّوش (مضمونين مدى الحياة)',
          '1x كيس مدرّج لقيس الصبيب هدية'
        ]
      },
      'pack-maison-5l': {
        name: 'باك الدار / الفيلا 5 لتر',
        idealFor: 'عايلة كبيرة / فيلا تستعمل الماء برشا',
        composition: [
          '4x موفّرات 5L/min للروبينيات',
          '2x منظّمات إينوكس للدوش 7L/min',
          '2x إيكو-ساك للتواليت 3 لتر ما يتحلّوش (مضمونين مدى الحياة)',
          '1x كيس مدرّج لقيس الصبيب هدية'
        ]
      }
    }
  }
};

export const ParticuliersPage = ({ setCurrentTab }) => {
  const { addToCart, language } = useCart();
  const t = TXT[language] || TXT.fr;

  // Les noms français restent ceux envoyés au panier et aux commandes
  const packs = [
    { id: 'pack-appartement-4l', price: 78.0, oldPrice: 99.0, image: '/products/pack_appartement_4l.webp' },
    { id: 'pack-appartement-5l', price: 78.0, oldPrice: 99.0, image: '/products/pack_appartement_5l.webp' },
    { id: 'pack-maison-4l', price: 129.0, oldPrice: 159.0, image: '/products/pack_maison_4l.webp' },
    { id: 'pack-maison-5l', price: 129.0, oldPrice: 159.0, image: '/products/pack_maison_5l.webp' },
  ].map((p) => ({ ...p, cartName: TXT.fr.packs[p.id].name, ...t.packs[p.id] }));

  return (
    <div className="py-10 space-y-16 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">

      {/* Header Banner */}
      <div className="bg-gradient-to-r from-brand-900 via-brand-800 to-skywater-600 text-white rounded-3xl p-8 sm:p-12 shadow-xl relative overflow-hidden">
        <div className="max-w-3xl space-y-4">
          <span className="px-3.5 py-1 bg-white/10 rounded-full text-sky-300 text-xs font-bold uppercase tracking-wider border border-white/20">
            {t.heroBadge}
          </span>
          <h1 className="text-3xl sm:text-5xl font-black font-serif tracking-tight text-white leading-tight">
            {t.heroTitle}
          </h1>
          <p className="text-slate-200 text-base sm:text-lg leading-relaxed">
            {t.heroText}
          </p>
        </div>
      </div>

      {/* The SONEDE Problem Explanation (from Pascal's docx) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-center bg-white rounded-3xl p-6 sm:p-10 border border-slate-200 shadow-md">

        <div className="lg:col-span-7 space-y-4">
          <div className="inline-flex items-center gap-2 text-amber-700 bg-amber-50 px-3 py-1 rounded-md text-xs font-bold">
            <AlertTriangle className="w-4 h-4" />
            <span>{t.problemBadge}</span>
          </div>

          <h2 className="text-2xl sm:text-3xl font-extrabold text-slate-900 font-serif">
            {t.problemTitle}
          </h2>

          <div className="space-y-3 text-slate-600 text-sm leading-relaxed">
            <p>
              {t.problem1[0]}<strong>{t.problem1[1]}</strong>{t.problem1[2]}
            </p>
            <p className="p-3 bg-red-50 border-s-4 border-red-500 rounded-e-xl text-red-900">
              <strong>{t.problem2[0]}</strong>{t.problem2[1]}<strong>{t.problem2[2]}</strong>{t.problem2[3]}
            </p>
            <p>
              {t.problem3[0]}<strong>{t.problem3[1]}</strong>{t.problem3[2]}<strong>{t.problem3[3]}</strong>{t.problem3[4]}
            </p>
          </div>

          <div className="pt-2 flex flex-wrap gap-4 text-xs font-bold text-slate-700">
            {t.checks.map((label) => (
              <span key={label} className="flex items-center gap-1 text-blue-700">
                <CheckCircle2 className="w-4 h-4 text-blue-600" /> {label}
              </span>
            ))}
          </div>
        </div>

        {/* Gift debitmeter highlight */}
        <div className="lg:col-span-5 bg-gradient-to-br from-blue-50 to-sky-50 border-2 border-dashed border-blue-300 rounded-2xl p-6 text-center space-y-4">
          <div className="w-14 h-14 rounded-2xl bg-blue-600 text-white flex items-center justify-center mx-auto shadow-md">
            <Gift className="w-7 h-7" />
          </div>
          <div>
            <span className="text-[11px] font-black uppercase text-blue-800 tracking-wider">{t.giftKicker}</span>
            <h3 className="text-xl font-black text-blue-950 mt-1">{t.giftTitle}</h3>
            <p className="text-xs text-blue-800 mt-2 leading-relaxed">
              {t.giftText[0]}<strong>{t.giftText[1]}</strong>{t.giftText[2]}
            </p>
          </div>
          <div className="p-3 bg-white rounded-xl text-xs font-bold text-blue-900 border border-blue-100">
            {t.giftFooter}
          </div>
        </div>

      </div>

      {/* Animated faucet: before / after */}
      <FaucetComparison />

      {/* Calculator for consumers */}
      <SavingsCalculator onSelectPack={(packId) => {
        const found = packs.find(p => p.id === packId) || packs[0];
        addToCart({
          id: found.id,
          name: found.cartName,
          price: found.price,
          image: found.image
        });
      }} />

      {/* Packs Showcase */}
      <div className="space-y-8">
        <div className="text-center max-w-2xl mx-auto">
          <h2 className="text-3xl font-extrabold text-slate-900 font-serif">
            {t.packsTitle}
          </h2>
          <p className="text-slate-600 text-sm mt-2">
            {t.packsText}
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
                  <div className="text-end">
                    <span className="text-xs text-slate-400 line-through me-1.5">{pack.oldPrice.toFixed(3)} {t.cur}</span>
                    <span className="text-2xl font-black text-brand-800">{pack.price.toFixed(3)} {t.cur}</span>
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
                    {t.composition}
                  </span>
                  {pack.composition.map((item, idx) => (
                    <div key={idx} className="flex items-start gap-2 text-xs text-slate-600">
                      <CheckCircle2 className="w-4 h-4 text-blue-600 shrink-0 mt-0.5" />
                      <span>{item}</span>
                    </div>
                  ))}
                </div>
              </div>

              <button
                onClick={() => addToCart({
                  id: pack.id,
                  name: pack.cartName,
                  price: pack.price,
                  image: pack.image
                })}
                className="w-full bg-gradient-to-r from-energy-500 to-energy-600 hover:from-energy-600 hover:to-energy-500 text-white font-extrabold py-3.5 px-4 rounded-xl text-sm flex items-center justify-center gap-2 shadow-md shadow-energy-500/25 transition-all hover:scale-[1.01]"
              >
                <ShoppingBag className="w-4 h-4" />
                <span>{t.addPack(pack.price.toFixed(3))}</span>
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* Individual products CTA banner */}
      <div className="bg-slate-100 rounded-3xl p-8 border border-slate-200 text-center space-y-4">
        <h3 className="text-xl font-bold text-slate-800">
          {t.unitTitle}
        </h3>
        <p className="text-xs text-slate-600 max-w-xl mx-auto">
          {t.unitText}
        </p>
        <button
          onClick={() => setCurrentTab('shop')}
          className="bg-brand-700 hover:bg-brand-800 text-white font-bold py-3 px-8 rounded-xl text-sm transition shadow-md shadow-brand-700/20"
        >
          {t.unitCta}
        </button>
      </div>

    </div>
  );
};
