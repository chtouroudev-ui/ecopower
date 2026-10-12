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

// Textes de la page d'accueil : français et darija tunisienne
const TXT = {
  fr: {
    cur: 'DT',
    heroBadge: 'Leader en Tunisie • Normes ISO & ACS Certifiées',
    heroTitle: ['Réduisez votre facture ', 'SONEDE & STEG', ' jusqu’à ', '60%'],
    heroText: 'La solution hydro-économe certifiée Delrin/Hostaform qui régule la pression en Tunisie. Même confort de jet, deux fois moins d’eau et de gaz consommés. Livré chez vous en 24h avec certificat de garantie 3 ans.',
    ctaOrder: 'Commander un Pack Éco',
    ctaSimulate: 'Simuler mes économies',
    trustWater: "Économie d'eau",
    trustGas: 'Économie gaz STEG',
    trustYears: '3 Ans',
    trustWarranty: 'Garantie & Certificat',
    cardOffer: 'Offre Spéciale -15%',
    cardKicker: 'Solution N°1 en Tunisie',
    cardTitle: 'Pack Appartement Éco 4L',
    cardSub: '2 Mousseurs Robinets + 1 Régulateur Douche + 1 Eco-Sac WC 3L',
    ttc: 'TTC',
    giftMeter: 'Sac Débitmètre Offert',
    addToCart: (price) => `Ajouter au Panier (${price} DT)`,
    cardFooter: 'Paiement à la livraison • Satisfait ou remboursé 14 jours',
    clipBadge: 'Installation Rapide Sans Outils',
    clipTitle: 'Où installer les économiseurs dans votre logement ?',
    clipText: "Chaque point d'eau de votre maison peut être équipé en moins de 2 minutes pour stopper le gaspillage mécanique SONEDE.",
    flowLabel: 'Débit :',
    step: 'Étape',
    waterSaving: 'Économie Eau',
    gasSaving: 'Économie Gaz',
    clipZones: [
      { zone: 'Évier Cuisine', flow: '4 ou 5 L/min', desc: 'Bague Inox + Cartouche Delrin anticalcaire.' },
      { zone: 'Lavabo Salle de Bain', flow: '4 L/min', desc: 'Jet doux aéré, supprime les éclaboussures.' },
      { zone: 'Douche & Flexible', flow: '5 ou 7 L/min', desc: 'Régulateur Inox placé sous le flexible de douche.' },
      { zone: 'Toilettes & WC', flow: '3 Litres / chasse', desc: 'Eco-Sac 3L imputrescible suspendu dans le réservoir.' },
    ],
    gasNA: 'N/A',
    packsKicker: 'Les Meilleures Ventes',
    packsTitle: 'Choisissez votre Pack Éco-Énergie',
    seeShop: 'Voir toute la boutique au détail',
    packs: {
      'pack-appartement-4l': {
        name: 'Pack Appartement 4L',
        badge: 'Plus Populaire',
        desc: 'Idéal Appartement F2 / F3 : 2 Mousseurs 4L/min + 1 Régulateur Douche + 1 Eco-Sac WC 3L + 1 Sac Débit-mètre Gratuit',
        features: ['Jusqu’à 60% d’économie d’eau', '+25% d’économie sur gaz STEG', 'Garantie 3 ans & Eco-Sac à vie', 'Sac Débit-mètre offert'],
      },
      'pack-maison-4l': {
        name: 'Pack Maison / Villa 4L',
        badge: 'Grand Logement',
        desc: 'Équipement complet Villa : 4 Mousseurs 4L/min + 2 Régulateurs Douche/Toilette + 2 Eco-Sacs WC 3L + Débit-mètre',
        features: ['Idéal pour 4 à 8 personnes', 'Double salle de bain', 'Économie annuelle > 280 DT', 'Installation en 2 minutes'],
      },
    },
    faqBadge: 'Foire Aux Questions',
    faqTitle: "Tout ce qu'il faut savoir sur l'hydro-économie",
    faqs: [
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
    ],
    finalBadge: 'Livraison 24-48h Partout en Tunisie',
    finalTitle: 'Passez à l’Hydro-Économie Dès Aujourd’hui',
    finalText: "Rejoignez plus de 2 000 foyers et 100 établissements équipés. Vos factures SONEDE et STEG diminuent dès le premier jour d'installation.",
    finalOrder: 'Commander Mon Pack en Ligne',
    finalPro: 'Espace Professionnel & Devis',
    finalTrust: ['✅ Garantie 3 ans', '✅ Satisfait ou Remboursé 14 jours', '✅ Paiement à la livraison'],
  },
  ar: {
    cur: 'د.ت',
    heroBadge: 'الأول في تونس • مطابق لمعايير ISO و ACS',
    heroTitle: ['نقّص في فاتورة ', 'الصوناد والستاغ', ' حتى لـ ', '60%'],
    heroText: 'الحل اللي يوفّر الماء، مصنوع من Delrin/Hostaform ومعتمد، ويظبط ضغط الماء في تونس. نفس الراحة متاع الماء، وتستهلك نص الماء ونص الغاز. يوصلك لدارك في 24 ساعة مع شهادة ضمان 3 سنين.',
    ctaOrder: 'اطلب باك إيكو',
    ctaSimulate: 'احسب قدّاش باش توفّر',
    trustWater: 'توفير في الماء',
    trustGas: 'توفير في غاز الستاغ',
    trustYears: '3 سنين',
    trustWarranty: 'ضمان وشهادة',
    cardOffer: 'عرض خاص -15%',
    cardKicker: 'الحل رقم 1 في تونس',
    cardTitle: 'باك الشقة إيكو 4L',
    cardSub: '2 مخفّضات للروبيني + 1 منظّم للدوش + 1 إيكو-ساك للتواليت 3L',
    ttc: 'بالأداءات',
    giftMeter: 'كيس قيس الصبيب هدية',
    addToCart: (price) => `زيد للسلة (${price} د.ت)`,
    cardFooter: 'الخلاص عند الاستلام • راضي ولا نرجعولك فلوسك في 14 يوم',
    clipBadge: 'تركيب سريع بلا عدّة',
    clipTitle: 'وين تركّب الموفّرات في دارك؟',
    clipText: 'كل نقطة ماء في دارك تنجم تجهّزها في أقل من دقيقتين، باش توقف التبذير اللي يعملو ضغط الصوناد.',
    flowLabel: 'الصبيب:',
    step: 'المرحلة',
    waterSaving: 'توفير الماء',
    gasSaving: 'توفير الغاز',
    clipZones: [
      { zone: 'مغسلة الكوجينة', flow: '4 ولا 5 L/min', desc: 'حلقة إينوكس + خرطوشة Delrin ضد الكلس.' },
      { zone: 'لافابو بيت البانو', flow: '4 L/min', desc: 'ماء ناعم فيه هواء، وما يطرطشش.' },
      { zone: 'الدوش والفليكسيبل', flow: '5 ولا 7 L/min', desc: 'منظّم إينوكس يتحط تحت فليكسيبل الدوش.' },
      { zone: 'التواليت', flow: '3 لتر في كل سيفون', desc: 'إيكو-ساك 3L ما يتحلّش، يتعلّق في الشاسة.' },
    ],
    gasNA: '—',
    packsKicker: 'الأكثر مبيعًا',
    packsTitle: 'اختار الباك متاعك',
    seeShop: 'شوف المتجر الكل',
    packs: {
      'pack-appartement-4l': {
        name: 'باك الشقة 4L',
        badge: 'الأكثر طلبًا',
        desc: 'مثالي للشقة S+1 / S+2 : 2 مخفّضات 4L/min + 1 منظّم للدوش + 1 إيكو-ساك 3L + كيس قيس الصبيب بلاش',
        features: ['توفير حتى 60% في الماء', 'توفير +25% في غاز الستاغ', 'ضمان 3 سنين والإيكو-ساك مضمون مدى الحياة', 'كيس قيس الصبيب هدية'],
      },
      'pack-maison-4l': {
        name: 'باك الدار / الفيلا 4L',
        badge: 'دار كبيرة',
        desc: 'تجهيز كامل للفيلا : 4 مخفّضات 4L/min + 2 منظّمات للدوش والتواليت + 2 إيكو-ساك 3L + كيس قيس الصبيب',
        features: ['مثالي من 4 لـ 8 أشخاص', 'زوز بيوت بانو', 'توفير في العام أكثر من 280 د.ت', 'يتركّب في دقيقتين'],
      },
    },
    faqBadge: 'أسئلة متكرّرة',
    faqTitle: 'كل شي لازمك تعرفو على توفير الماء',
    faqs: [
      {
        q: 'علاش ضغط الصوناد يطيّر الفاتورة في تونس؟',
        a: 'في أوروبا الضغط مظبوط على 3 بار (12 لتر في الدقيقة في الروبيني). أما في تونس، ضغط الصوناد موش مظبوط ويتبدّل من حومة لحومة. في أكثر من 80% من الديار، هذا يعطي صبيب زايد يوصل لـ 20 ولا 24 لتر في الدقيقة! تستهلك وتخلّص الضعف وإنت ما تعرفش.'
      },
      {
        q: 'نخسرو الراحة ولا الضغط تحت الدوش؟',
        a: 'لا أبدًا! الموفّرات متاعنا فيها نظام تهوئة مسجّل تحت ماركة HOSTAFORM / DELRIN. الماء يتخلط بالهواء تحت الضغط، ويعطيك جت قوي وواسع ومريّح، وتستهلك 60% ماء أقل.'
      },
      {
        q: 'شنوّة التأثير على فاتورة غاز الستاغ؟',
        a: 'الماء السخون الكل اللي تستعملو في الدوش ولا في الروبيني لازمو يتسخّن بالشوديار ولا بالشوفو متاع الغاز. كي تقسم الماء السخون على زوز، تنقّص أوتوماتيكيًا من 25% لـ 40% من الغاز اللي يلزم باش يسخّنو!'
      },
      {
        q: 'التركيب يلزمو بلومبي ولا عدّة؟',
        a: 'لا، ما يلزمك حتى عدّة ولا خبرة في البلومبري. التركيب ياخو أقل من دقيقتين: تفكّ الراس القديم بيدك وتسكّر في بلاصتو المنظّم متاع EcoPower.'
      },
      {
        q: 'كيفاش يخدم الضمان والخلاص؟',
        a: 'الأجهزة متاعنا الكل عندها ضمان 3 سنين (والإيكو-ساك متاع التواليت مضمون مدى الحياة). نوصلو لكامل تونس في 24 لـ 48 ساعة، والخلاص كاش عند الاستلام. وعندك 14 يوم «راضي ولا نرجعولك فلوسك».'
      }
    ],
    finalBadge: 'توصيل في 24-48 ساعة لكامل تونس',
    finalTitle: 'ابدا وفّر في الماء من اليوم',
    finalText: 'التحق بأكثر من 2000 دار و100 مؤسسة مجهّزة. فواتير الصوناد والستاغ تنقص من أول نهار تركّب فيه.',
    finalOrder: 'اطلب الباك متاعي أونلاين',
    finalPro: 'فضاء المحترفين والديفي',
    finalTrust: ['✅ ضمان 3 سنين', '✅ راضي ولا نرجعولك فلوسك في 14 يوم', '✅ الخلاص عند الاستلام'],
  },
};

export const HomePage = ({ setCurrentTab }) => {
  const { addToCart, language } = useCart();
  const [openFaq, setOpenFaq] = useState(null);
  const t = TXT[language] || TXT.fr;

  // Quick packs for showcase
  const featuredPacks = [
    {
      id: 'pack-appartement-4l',
      name: 'Pack Appartement 4L',
      price: 78.0,
      oldPrice: 99.0,
      image: '/products/pack_appartement_4l.webp',
    },
    {
      id: 'pack-maison-4l',
      name: 'Pack Maison / Villa 4L',
      price: 129.0,
      oldPrice: 159.0,
      image: '/products/pack_maison_4l.webp',
    }
  ];

  // Clip diagram zones (from Pascal's email RETOUCHES CLIP)
  const clipZones = [
    { waterSaved: '+60%', gasSaved: '+25%', img: '/products/bague_mousseur_complet.jpg' },
    { waterSaved: '+60%', gasSaved: '+25%', img: '/products/cartouche_hydro_verte.jpg' },
    { waterSaved: '+60%', gasSaved: '+25%', img: '/products/bague_mousseur_grille_bleue.jpg' },
    { waterSaved: '-30%', gasSaved: null, img: '/products/ecosac_wc_3l.jpg' },
  ].map((z, idx) => ({ ...z, ...t.clipZones[idx], gasSaved: z.gasSaved ?? t.gasNA }));

  return (
    <div className="space-y-16 sm:space-y-24">

      {/* 1. HERO SECTION */}
      <section className="relative overflow-hidden pt-8 pb-16 sm:pt-16 sm:pb-24 bg-gradient-to-b from-brand-50/60 via-white to-slate-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 items-center">

            {/* Left Column: Copy & CTAs */}
            <div className="lg:col-span-7 space-y-6 text-center lg:text-start">

              <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-brand-100 text-brand-800 text-xs font-bold tracking-wide">
                <Sparkles className="w-4 h-4 text-brand-600" />
                <span>{t.heroBadge}</span>
              </div>

              <h1 className="text-4xl sm:text-5xl lg:text-6xl font-black text-slate-900 tracking-tight leading-[1.15] font-serif">
                {t.heroTitle[0]}<span className="text-brand-700">{t.heroTitle[1]}</span>{t.heroTitle[2]}<span className="text-energy-500">{t.heroTitle[3]}</span>
              </h1>

              <p className="text-base sm:text-lg text-slate-600 leading-relaxed max-w-2xl mx-auto lg:mx-0">
                {t.heroText}
              </p>

              {/* CTAs */}
              <div className="flex flex-col sm:flex-row items-center justify-center lg:justify-start gap-3 pt-2">
                <button
                  onClick={() => setCurrentTab('shop')}
                  className="w-full sm:w-auto bg-gradient-to-r from-energy-500 to-energy-600 hover:from-energy-600 hover:to-energy-500 text-white font-extrabold px-8 py-4 rounded-2xl text-base shadow-xl shadow-energy-500/30 flex items-center justify-center gap-2 transition-all hover:scale-105 active:scale-95"
                >
                  <ShoppingBag className="w-5 h-5" />
                  <span>{t.ctaOrder}</span>
                </button>

                <button
                  onClick={() => setCurrentTab('calculator')}
                  className="w-full sm:w-auto bg-white hover:bg-slate-50 text-slate-800 border-2 border-slate-200 font-bold px-7 py-4 rounded-2xl text-base flex items-center justify-center gap-2 transition-all hover:border-brand-500 hover:text-brand-700"
                >
                  <span>{t.ctaSimulate}</span>
                  <ArrowRight className="w-4 h-4 rtl:rotate-180" />
                </button>
              </div>

              {/* Trust bullets */}
              <div className="pt-4 grid grid-cols-3 gap-2 border-t border-slate-200/80 text-center lg:text-start">
                <div>
                  <div className="text-xl sm:text-2xl font-black text-brand-800">+60%</div>
                  <div className="text-[11px] text-slate-500 font-semibold">{t.trustWater}</div>
                </div>
                <div>
                  <div className="text-xl sm:text-2xl font-black text-energy-500">+25%</div>
                  <div className="text-[11px] text-slate-500 font-semibold">{t.trustGas}</div>
                </div>
                <div>
                  <div className="text-xl sm:text-2xl font-black text-blue-600">{t.trustYears}</div>
                  <div className="text-[11px] text-slate-500 font-semibold">{t.trustWarranty}</div>
                </div>
              </div>

            </div>

            {/* Right Column: Hero Visual Product Card */}
            <div className="lg:col-span-5 relative">
              <div className="relative mx-auto max-w-md bg-white rounded-3xl p-6 shadow-2xl border border-slate-200/90 overflow-hidden">
                <div className="absolute top-4 end-4 bg-energy-500 text-white text-[10px] font-black uppercase px-3 py-1 rounded-full shadow-xs">
                  {t.cardOffer}
                </div>

                <div className="text-xs font-bold text-brand-700 uppercase tracking-wider mb-2">
                  {t.cardKicker}
                </div>
                <h3 className="text-2xl font-black text-slate-900 font-serif">
                  {t.cardTitle}
                </h3>
                <p className="text-xs text-slate-500 mt-1">
                  {t.cardSub}
                </p>

                <div className="my-5 rounded-2xl bg-slate-50 p-4 border border-slate-100 flex items-center justify-center">
                  <img
                    src="/products/pack_appartement_4l.webp"
                    alt="Pack EcoPower"
                    className="h-52 object-contain drop-shadow-md hover:scale-105 transition-transform"
                  />
                </div>

                <div className="flex items-baseline justify-between mb-4">
                  <div>
                    <span className="text-xs text-slate-400 line-through me-2">99.000 {t.cur}</span>
                    <span className="text-3xl font-black text-brand-900">78.000 {t.cur}</span>
                    <span className="text-xs text-slate-500 ms-1">{t.ttc}</span>
                  </div>
                  <span className="text-xs font-bold text-blue-700 bg-blue-50 px-2.5 py-1 rounded-md">
                    {t.giftMeter}
                  </span>
                </div>

                <button
                  onClick={() => addToCart({
                    id: 'pack-appartement-4l',
                    name: 'Pack Appartement 4 Litres',
                    price: 78.0,
                    image: '/products/pack_appartement_4l.webp'
                  })}
                  className="w-full bg-brand-700 hover:bg-brand-800 text-white font-black py-3 px-4 rounded-xl text-sm flex items-center justify-center gap-2 shadow-md shadow-brand-700/20 transition-all hover:scale-[1.02]"
                >
                  <ShoppingBag className="w-4 h-4" />
                  <span>{t.addToCart(78)}</span>
                </button>

                <p className="text-center text-[11px] text-slate-600 mt-3 flex items-center justify-center gap-1.5">
                  <CheckCircle2 className="w-3.5 h-3.5 text-blue-600" />
                  {t.cardFooter}
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
            <span>{t.clipBadge}</span>
          </div>
          <h2 className="text-3xl sm:text-4xl font-extrabold text-slate-900 font-serif">
            {t.clipTitle}
          </h2>
          <p className="text-slate-600 text-sm sm:text-base mt-2">
            {t.clipText}
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
                    {t.flowLabel} {item.flow}
                  </span>
                  <span className="text-[10px] font-black text-slate-400">{t.step} {idx + 1}</span>
                </div>

                <h3 className="font-extrabold text-base text-slate-900 mb-1">{item.zone}</h3>
                <p className="text-xs text-slate-500 leading-relaxed mb-4">{item.desc}</p>
              </div>

              {/* Savings badges */}
              <div className="pt-3 border-t border-slate-100 grid grid-cols-2 gap-2 text-center text-xs">
                <div className="bg-skywater-50 text-skywater-800 p-2 rounded-xl">
                  <div className="font-black text-sm text-skywater-700">{item.waterSaved}</div>
                  <div className="text-[10px] font-semibold text-slate-500">{t.waterSaving}</div>
                </div>
                <div className="bg-amber-50 text-amber-900 p-2 rounded-xl">
                  <div className="font-black text-sm text-energy-600">{item.gasSaved}</div>
                  <div className="text-[10px] font-semibold text-slate-500">{t.gasSaving}</div>
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
              price: 78.0,
              image: '/products/pack_appartement_4l.webp'
            });
          } else {
            addToCart({
              id: 'pack-maison-4l',
              name: 'Pack Maison / Villa 4 Litres',
              price: 129.0,
              image: '/products/pack_maison_4l.webp'
            });
          }
        }} />
      </section>

      {/* 4. PACKS VEDETTES DU SITE */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-end mb-8 gap-4">
          <div>
            <div className="text-xs font-bold text-brand-700 uppercase tracking-wider mb-1">
              {t.packsKicker}
            </div>
            <h2 className="text-3xl font-black text-slate-900 font-serif">
              {t.packsTitle}
            </h2>
          </div>
          <button
            onClick={() => setCurrentTab('shop')}
            className="text-xs font-bold text-brand-700 hover:text-brand-900 flex items-center gap-1 group"
          >
            <span>{t.seeShop}</span>
            <ArrowRight className="w-4 h-4 rtl:rotate-180 group-hover:translate-x-1 rtl:group-hover:-translate-x-1 transition-transform" />
          </button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          {featuredPacks.map((pack) => {
            const tp = t.packs[pack.id];
            return (
            <div
              key={pack.id}
              className="bg-white rounded-3xl border border-slate-200/90 p-6 sm:p-8 shadow-md hover:shadow-xl transition-all flex flex-col justify-between"
            >
              <div>
                <div className="flex justify-between items-start mb-4">
                  <span className="px-3 py-1 bg-brand-100 text-brand-800 text-xs font-bold rounded-full">
                    {tp.badge}
                  </span>
                  <div className="flex items-center gap-1 text-amber-400">
                    <Star className="w-4 h-4 fill-amber-400" />
                    <span className="text-xs font-black text-slate-800" dir="ltr">4.9 / 5</span>
                  </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-12 gap-6 items-center mb-6">
                  <div className="sm:col-span-5 h-44 rounded-2xl bg-slate-50 border border-slate-100 flex items-center justify-center p-3">
                    <img
                      src={pack.image}
                      alt={tp.name}
                      className="max-h-full max-w-full object-contain"
                    />
                  </div>
                  <div className="sm:col-span-7">
                    <h3 className="text-xl font-black text-slate-900 font-serif">{tp.name}</h3>
                    <p className="text-xs text-slate-600 mt-1 leading-relaxed">{tp.desc}</p>
                    <div className="mt-3">
                      <span className="text-xs text-slate-400 line-through me-2">{pack.oldPrice.toFixed(3)} {t.cur}</span>
                      <span className="text-2xl font-black text-brand-800">{pack.price.toFixed(3)} {t.cur}</span>
                    </div>
                  </div>
                </div>

                <div className="space-y-2 mb-6 text-xs text-slate-700">
                  {tp.features.map((feat, fidx) => (
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
                <span>{t.addToCart(pack.price.toFixed(3))}</span>
              </button>
            </div>
            );
          })}
        </div>
      </section>

      {/* 5. CARROUSEL DES RÉFÉRENCES (Hotels, Cliniques, etc.) */}
      <ReferencesCarousel />

      {/* 6. FAQ ACCORDION */}
      <section className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center mb-10">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-slate-100 text-slate-700 text-xs font-bold uppercase tracking-wider mb-2">
            <HelpCircle className="w-4 h-4 text-brand-600" />
            <span>{t.faqBadge}</span>
          </div>
          <h2 className="text-3xl font-extrabold text-slate-900 font-serif">
            {t.faqTitle}
          </h2>
        </div>

        <div className="space-y-3">
          {t.faqs.map((faq, idx) => {
            const isOpen = openFaq === idx;
            return (
              <div
                key={idx}
                className="bg-white rounded-2xl border border-slate-200/80 overflow-hidden shadow-xs transition"
              >
                <button
                  onClick={() => setOpenFaq(isOpen ? null : idx)}
                  className="w-full text-start p-5 flex items-center justify-between gap-4 font-bold text-sm sm:text-base text-slate-900 hover:text-brand-700 transition"
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
              {t.finalBadge}
            </span>
            <h2 className="text-3xl sm:text-5xl font-black font-serif tracking-tight text-white">
              {t.finalTitle}
            </h2>
            <p className="text-slate-200 text-sm sm:text-base">
              {t.finalText}
            </p>
            <div className="pt-2 flex flex-col sm:flex-row items-center justify-center gap-3">
              <button
                onClick={() => setCurrentTab('shop')}
                className="w-full sm:w-auto bg-gradient-to-r from-energy-500 to-energy-600 hover:from-energy-600 hover:to-energy-500 text-white font-extrabold px-8 py-4 rounded-2xl text-base shadow-xl transition-all hover:scale-105"
              >
                {t.finalOrder}
              </button>
              <button
                onClick={() => setCurrentTab('professionnels')}
                className="w-full sm:w-auto bg-white/10 hover:bg-white/20 text-white border border-white/30 font-bold px-7 py-4 rounded-2xl text-base transition"
              >
                {t.finalPro}
              </button>
            </div>
            <div className="pt-4 text-xs text-slate-300 flex flex-wrap items-center justify-center gap-3">
              <span>{t.finalTrust[0]}</span>
              <span>•</span>
              <span>{t.finalTrust[1]}</span>
              <span>•</span>
              <span>{t.finalTrust[2]}</span>
            </div>
          </div>
        </div>
      </section>

    </div>
  );
};
