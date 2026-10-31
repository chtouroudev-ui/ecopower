import React, { useMemo, useState } from 'react';
import {
  ArrowRight,
  Building2,
  Calculator,
  ChevronDown,
  Droplets,
  Flame,
  Home,
  Info,
  RotateCcw,
  Timer,
  TrendingDown,
  Wallet,
} from 'lucide-react';
import { useCart } from '../context/CartContext';
import {
  PRIX_GAZ,
  PRIX_HOTEL,
  SONEDE_TRANCHES,
  T_FROIDE,
  T_USAGE,
  fmt,
  simulerFoyer,
  simulerHotel,
} from '../lib/simulator';

const HOTEL_DEFAUTS = {
  chambres: 100,
  occupation: 60,
  personnesParChambre: 1.7,
  dIniDouche: 12,
  dEcoDouche: 7,
  tDouche: 8,
  dIniLavabo: 8,
  dEcoLavabo: 3,
  tLavabo: 1,
  freqLavabo: 4,
  dEcoFlex: 0,
  tFlex: 0.5,
  freqFlex: 3,
  ecoSac: false,
  chasseLitres: 10,
  chassesParClient: 4,
  prixEcoSac: 22.9,
};

const FOYER_DEFAUTS = {
  personnes: 4,
  dIniDouche: 12,
  dEcoDouche: 7,
  tDouche: 8,
  dIniRobinet: 12,
  dEcoRobinet: 4,
  tLavabo: 3,
  tCuisine: 10,
  chasses: 4,
};

const PACKS = {
  appartement: { id: 'appartement', prix: 78 },
  maison: { id: 'maison', prix: 129 },
};

/* ---------- Textes : français et darija tunisienne ---------- */

const TXT = {
  fr: {
    cur: 'DT',
    days: (n) => `${n} jours`,
    months: (n) => `${n} mois`,
    savedEst: 'Économies estimées',
    perYear: 'DT / an',
    soit: (m, d) => `soit ${m} DT par mois et ${d} DT par jour`,
    kpiInvest: 'Investissement',
    kpiRoi: 'Amortissement',
    kpiWater: 'Eau économisée',
    kpiEnergy: 'Énergie économisée',
    m3Year: 'm³/an',
    kwhYear: 'kWh/an',
    ofWater: "d'eau",
    roiLabel: 'Retour sur investissement',
    roiGoal: 'objectif : moins de 90 jours',
    tableTitle: "Consommation journalière par point d'usage",
    colPoint: 'Poste',
    colWithout: 'Sans',
    colWith: 'Avec',
    colGain: 'Gain',
    coldWater: 'eau froide',
    totalDay: 'Total / jour',
    pointLabels: {},
    detail: (d) => d,
    tranche: (l) => l,
    waterDay: 'Eau SONEDE / jour',
    gasDay: 'Chauffage gaz STEG / jour',
    without: 'Sans',
    with: 'Avec',
    methodTitle: 'Méthode de calcul',
    badge: 'Simulateur SONEDE & STEG',
    title: 'Calculez vos économies et votre amortissement',
    subtitle: 'Résultats instantanés en dinars, selon les tarifs SONEDE par tranche et le prix du gaz STEG.',
    tabHome: 'Particulier',
    tabHotel: 'Hôtel',
    hotelSection: 'Établissement',
    rooms: 'Nombre de chambres',
    roomsUnit: 'ch.',
    occupancy: "Taux d'occupation",
    perRoom: 'Personnes par chambre occupée',
    persUnit: 'pers.',
    hotelHint: (n) => `≈ ${n} clients par jour. Périmètre : chambres uniquement (hors cuisine, restaurant, piscine, spa).`,
    roomEquip: 'Équipement par chambre',
    showerSaver: (p) => `Économiseur douche (${p} DT)`,
    basinSaver: 'Économiseur lavabo',
    black: 'noir',
    pink: 'rose',
    flexLabel: 'Flexible toilette / douchette WC',
    none: 'Sans',
    ecoSac: (p) => `Eco-Sac WC 3 L (${p} DT)`,
    no: 'Non',
    yes: 'Oui',
    costRoom: 'Coût par chambre',
    advanced: 'Paramètres avancés (débits et durées)',
    showerFlow: 'Débit actuel douche',
    showerTime: 'Durée de douche',
    minClient: 'min/client',
    basinFlow: 'Débit actuel lavabo',
    basinTime: 'Durée par usage lavabo',
    min: 'min',
    basinUses: 'Usages lavabo',
    perClientDay: '/client/j',
    flexTime: 'Durée par usage flexible',
    flexUses: 'Usages flexible',
    flushes: 'Chasses WC',
    reset: 'Revenir aux valeurs par défaut',
    audit: 'Demander un audit gratuit',
    hotelInvest: (n, c, total) => (
      <>
        Investissement = {n} chambres × {c} DT = <strong className="text-slate-900">{total} DT</strong>. Diagnostic, test de débit et pose
        réalisés par nos équipes.
      </>
    ),
    homeSection: 'Votre foyer',
    people: 'Personnes au foyer',
    minPers: 'min/pers.',
    basin: 'Lavabo',
    minPersDay: 'min/pers./j',
    kitchen: 'Évier cuisine',
    minDay: 'min/j',
    perPersDay: '/pers./j',
    installSection: 'Votre installation',
    showerHint: 'En Tunisie, la pression non régulée peut doubler le débit. Testez-le avec le sac débit-mètre offert.',
    tapFlow: 'Débit actuel robinets',
    showerReg: 'Régulateur douche',
    tapAerators: 'Mousseurs robinets',
    packLabels: { appartement: 'Pack Appartement', maison: 'Pack Maison / Villa' },
    recommended: 'Recommandé :',
    refund: 'satisfait ou remboursé 14 jours',
    orderPack: (label, prix) => `Commander le ${label} (${prix} DT)`,
  },
  ar: {
    cur: 'د.ت',
    days: (n) => `${n} يوم`,
    months: (n) => `${n} شهر`,
    savedEst: 'التوفير المتوقّع',
    perYear: 'د.ت في العام',
    soit: (m, d) => `يعني ${m} د.ت في الشهر و${d} د.ت في النهار`,
    kpiInvest: 'الاستثمار',
    kpiRoi: 'ترجيع الفلوس',
    kpiWater: 'الماء الموفّر',
    kpiEnergy: 'الطاقة الموفّرة',
    m3Year: 'm³ في العام',
    kwhYear: 'kWh في العام',
    ofWater: 'في الماء',
    roiLabel: 'مدّة ترجيع الفلوس',
    roiGoal: 'الهدف: أقل من 90 يوم',
    tableTitle: 'الاستهلاك في النهار حسب كل نقطة ماء',
    colPoint: 'البلاصة',
    colWithout: 'بلا',
    colWith: 'مع',
    colGain: 'الربح',
    coldWater: 'ماء بارد',
    totalDay: 'المجموع في النهار',
    pointLabels: {
      douche: 'الدوش',
      lavabo: 'اللافابو',
      cuisine: 'مغسلة الكوجينة',
      flex: 'فليكسيبل التواليت',
      wc: 'شاسة التواليت (إيكو-ساك)',
    },
    detail: (d) => d.replace('→', '←').replace('L/chasse', 'L/سيفون').replace('Sans économiseur', 'بلا موفّر'),
    tranche: (l) => l.replace(' à ', ' لـ '),
    waterDay: 'ماء الصوناد في النهار',
    gasDay: 'تسخين بغاز الستاغ في النهار',
    without: 'بلا',
    with: 'مع',
    methodTitle: 'كيفاش نحسبو',
    badge: 'حاسبة الصوناد والستاغ',
    title: 'احسب قدّاش توفّر وفي قدّاش ترجعلك فلوسك',
    subtitle: 'نتايج فورية بالدينار، حسب تعريفة الصوناد بالشرائح وسوم غاز الستاغ.',
    tabHome: 'عايلة',
    tabHotel: 'نزل',
    hotelSection: 'المؤسسة',
    rooms: 'عدد البيوت',
    roomsUnit: 'بيت',
    occupancy: 'نسبة الإشغال',
    perRoom: 'عدد الأشخاص في كل بيت',
    persUnit: 'شخص',
    hotelHint: (n) => `≈ ${n} حريف في النهار. الحساب على البيوت برك (بلا كوجينة، ريستوران، بيسين ولا سبا).`,
    roomEquip: 'التجهيز في كل بيت',
    showerSaver: (p) => `موفّر الدوش (${p} د.ت)`,
    basinSaver: 'موفّر اللافابو',
    black: 'كحل',
    pink: 'روز',
    flexLabel: 'فليكسيبل / دوش التواليت',
    none: 'بلا',
    ecoSac: (p) => `إيكو-ساك التواليت 3 L (${p} د.ت)`,
    no: 'لا',
    yes: 'إيه',
    costRoom: 'الكلفة في كل بيت',
    advanced: 'إعدادات متقدّمة (الصبيب والمدّة)',
    showerFlow: 'صبيب الدوش توّا',
    showerTime: 'مدّة الدوش',
    minClient: 'دقيقة/حريف',
    basinFlow: 'صبيب اللافابو توّا',
    basinTime: 'مدّة كل استعمال للافابو',
    min: 'دقيقة',
    basinUses: 'عدد استعمالات اللافابو',
    perClientDay: '/حريف/نهار',
    flexTime: 'مدّة كل استعمال للفليكسيبل',
    flexUses: 'عدد استعمالات الفليكسيبل',
    flushes: 'عدد السيفونات',
    reset: 'رجّع القيم الأصلية',
    audit: 'اطلب معاينة بلاش',
    hotelInvest: (n, c, total) => (
      <>
        الاستثمار = {n} بيت × {c} د.ت = <strong className="text-slate-900">{total} د.ت</strong>. التشخيص، تجربة الصبيب والتركيب يعملهم
        الفريق متاعنا.
      </>
    ),
    homeSection: 'دارك',
    people: 'عدد الأشخاص في الدار',
    minPers: 'دقيقة/شخص',
    basin: 'اللافابو',
    minPersDay: 'دقيقة/شخص/نهار',
    kitchen: 'مغسلة الكوجينة',
    minDay: 'دقيقة/نهار',
    perPersDay: '/شخص/نهار',
    installSection: 'التجهيز متاعك',
    showerHint: 'في تونس، الضغط اللي موش مظبوط ينجم يضاعف الصبيب. جرّبو بكيس قيس الصبيب اللي نهديوهولك.',
    tapFlow: 'صبيب الروبينيات توّا',
    showerReg: 'منظّم الدوش',
    tapAerators: 'مخفّضات الروبينيات',
    packLabels: { appartement: 'باك الشقة', maison: 'باك الدار / الفيلا' },
    recommended: 'ننصحوك بـ:',
    refund: 'راضي ولا نرجعولك فلوسك في 14 يوم',
    orderPack: (label, prix) => `اطلب ${label} (${prix} د.ت)`,
  },
};

const useTxt = () => {
  const { language } = useCart();
  return TXT[language] || TXT.fr;
};

/* ---------- Petits composants d'interface ---------- */

const Slider = ({ label, value, unit, min, max, step = 1, onChange, hint }) => (
  <div>
    <div className="flex items-baseline justify-between gap-3 mb-1.5">
      <label className="text-sm font-semibold text-slate-700">{label}</label>
      <span dir="auto" className="text-sm font-bold text-blue-800 tabular-nums whitespace-nowrap">
        {fmt(value, step < 1 ? 1 : 0)} {unit}
      </span>
    </div>
    <input
      type="range"
      min={min}
      max={max}
      step={step}
      value={value}
      onChange={(e) => onChange(parseFloat(e.target.value))}
      className="w-full h-2 bg-slate-200 rounded-full appearance-none cursor-pointer accent-blue-600"
      aria-label={label}
    />
    {hint && <p className="text-[11px] text-slate-400 mt-1">{hint}</p>}
  </div>
);

const Choice = ({ label, value, options, onChange }) => (
  <div>
    <div className="text-sm font-semibold text-slate-700 mb-1.5">{label}</div>
    <div className="flex flex-wrap gap-1.5">
      {options.map((o) => (
        <button
          key={String(o.value)}
          type="button"
          onClick={() => onChange(o.value)}
          className={`px-3 py-1.5 rounded-lg text-xs font-bold border transition-colors ${
            value === o.value
              ? 'bg-blue-600 border-blue-600 text-white'
              : 'bg-white border-slate-200 text-slate-600 hover:border-blue-300'
          }`}
        >
          {o.label}
        </button>
      ))}
    </div>
  </div>
);

const Section = ({ title, icon: Icon, children }) => (
  <div className="rounded-2xl border border-slate-200 bg-slate-50/60 p-4 sm:p-5 space-y-4">
    <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-slate-500">
      {Icon && <Icon className="w-4 h-4 text-blue-600" />}
      {title}
    </div>
    {children}
  </div>
);

const Kpi = ({ label, value, sub }) => (
  <div className="rounded-xl bg-white/10 border border-white/15 p-3">
    <div className="text-[11px] uppercase tracking-wide text-sky-200 font-semibold">{label}</div>
    <div className="text-lg font-black text-white tabular-nums">{value}</div>
    {sub && <div className="text-[11px] text-blue-200">{sub}</div>}
  </div>
);

/* ---------- Résultats communs ---------- */

const Resultats = ({ r, cta, extra }) => {
  const t = useTxt();
  const roiTexte =
    r.roiJours === Infinity
      ? '—'
      : r.roiJours < 60
        ? t.days(fmt(Math.ceil(r.roiJours)))
        : t.months(fmt(r.roiMois, 1));
  const progression = Number.isFinite(r.roiJours) ? Math.min(100, (90 / Math.max(r.roiJours, 1)) * 100) : 0;

  return (
    <div className="space-y-5">
      <div className="bg-gradient-to-br from-blue-950 via-blue-900 to-blue-800 text-white rounded-2xl p-6 shadow-xl relative overflow-hidden">
        <div className="absolute -end-16 -top-16 w-56 h-56 bg-sky-400/20 rounded-full blur-3xl pointer-events-none" />
        <div className="relative">
          <div className="text-xs uppercase tracking-wider text-sky-300 font-bold">{t.savedEst}</div>
          <div className="text-4xl sm:text-5xl font-black tracking-tight tabular-nums mt-1">
            {fmt(r.ecoAn)} <span className="text-xl font-bold text-sky-300">{t.perYear}</span>
          </div>
          <div className="text-sm text-blue-200 mt-1">
            {t.soit(fmt(r.ecoMois), fmt(r.ecoJour, 2))}
          </div>

          <div className="grid grid-cols-2 gap-2.5 mt-5">
            <Kpi label={t.kpiInvest} value={`${fmt(r.investissement, r.investissement < 1000 ? 1 : 0)} ${t.cur}`} />
            <Kpi label={t.kpiRoi} value={roiTexte} sub={Number.isFinite(r.roiJours) ? t.days(fmt(r.roiJours)) : null} />
            <Kpi label={t.kpiWater} value={`${fmt(r.m3EconomisesAn)} ${t.m3Year}`} sub={`−${fmt(r.pourcentage)} % ${t.ofWater}`} />
            <Kpi label={t.kpiEnergy} value={`${fmt(r.kwhEconomisesAn)} ${t.kwhYear}`} />
          </div>

          <div className="mt-5">
            <div className="flex justify-between text-[11px] text-sky-200 mb-1">
              <span>{t.roiLabel}</span>
              <span>{t.roiGoal}</span>
            </div>
            <div className="h-2 rounded-full bg-white/15 overflow-hidden">
              <div className="h-full bg-sky-400 rounded-full transition-all duration-500" style={{ width: `${progression}%` }} />
            </div>
          </div>

          {cta && <div className="mt-6">{cta}</div>}
        </div>
      </div>

      {/* Tableau par point d'usage */}
      <div className="rounded-2xl border border-slate-200 overflow-hidden bg-white">
        <div className="px-4 py-3 bg-slate-50 border-b border-slate-200 text-xs font-bold uppercase tracking-wider text-slate-500">
          {t.tableTitle}
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-[11px] uppercase text-slate-500 border-b border-slate-100">
                <th className="text-start font-semibold ps-3 sm:px-4 py-2">{t.colPoint}</th>
                <th className="text-end font-semibold px-2 sm:px-4 py-2">{t.colWithout}</th>
                <th className="text-end font-semibold px-2 sm:px-4 py-2">{t.colWith}</th>
                <th className="text-end font-semibold px-2 sm:px-4 py-2">{t.colGain}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {r.points.map((p) => (
                <tr key={p.key}>
                  <td className="ps-3 pe-1 sm:px-4 py-2.5">
                    <div className="font-semibold text-slate-800">{t.pointLabels[p.key] || p.label}</div>
                    <div className="text-[11px] text-slate-400">{t.detail(p.detail)}{p.dT ? ` · ΔT ${p.dT} °C` : ` · ${t.coldWater}`}</div>
                  </td>
                  <td className="px-2 sm:px-4 py-2.5 text-end tabular-nums whitespace-nowrap text-slate-500"><bdi>{fmt(p.sans)} L</bdi></td>
                  <td className="px-2 sm:px-4 py-2.5 text-end tabular-nums whitespace-nowrap font-semibold text-blue-800"><bdi>{fmt(p.avec)} L</bdi></td>
                  <td className="px-2 sm:px-4 py-2.5 text-end tabular-nums whitespace-nowrap text-slate-700"><bdi>{p.sans > p.avec ? `−${fmt(p.sans - p.avec)} L` : '—'}</bdi></td>
                </tr>
              ))}
              <tr className="bg-blue-50/60 font-bold">
                <td className="ps-3 pe-1 sm:px-4 py-2.5 text-slate-900">{t.totalDay}</td>
                <td className="px-2 sm:px-4 py-2.5 text-end tabular-nums whitespace-nowrap"><bdi>{fmt(r.vSans)} L</bdi></td>
                <td className="px-2 sm:px-4 py-2.5 text-end tabular-nums whitespace-nowrap text-blue-800"><bdi>{fmt(r.vAvec)} L</bdi></td>
                <td className="px-2 sm:px-4 py-2.5 text-end tabular-nums whitespace-nowrap"><bdi>−{fmt(r.vSans - r.vAvec)} L</bdi></td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      {/* Coûts */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div className="rounded-2xl border border-slate-200 p-4 bg-white">
          <div className="flex items-center gap-2 text-sm font-bold text-slate-800">
            <Droplets className="w-4 h-4 text-blue-600" /> {t.waterDay}
          </div>
          <div className="mt-2 flex justify-between text-sm">
            <span className="text-slate-500">{t.without} ({t.tranche(r.eauSans.tranche.label)})</span>
            <span className="tabular-nums">{fmt(r.eauSans.cout, 2)} {t.cur}</span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-slate-500">{t.with} ({t.tranche(r.eauAvec.tranche.label)})</span>
            <span className="tabular-nums font-semibold text-blue-800">{fmt(r.eauAvec.cout, 2)} {t.cur}</span>
          </div>
        </div>
        <div className="rounded-2xl border border-slate-200 p-4 bg-white">
          <div className="flex items-center gap-2 text-sm font-bold text-slate-800">
            <Flame className="w-4 h-4 text-orange-500" /> {t.gasDay}
          </div>
          <div className="mt-2 flex justify-between text-sm">
            <span className="text-slate-500">{t.without} ({fmt(r.kwhSans)} kWh)</span>
            <span className="tabular-nums">{fmt(r.gazSans, 2)} {t.cur}</span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-slate-500">{t.with} ({fmt(r.kwhAvec)} kWh)</span>
            <span className="tabular-nums font-semibold text-blue-800">{fmt(r.gazAvec, 2)} {t.cur}</span>
          </div>
        </div>
      </div>

      {extra}
      <Methodologie r={r} />
    </div>
  );
};

const Methodologie = ({ r }) => {
  const [open, setOpen] = useState(false);
  const { language } = useCart();
  const t = TXT[language] || TXT.fr;
  const isAr = language === 'ar';
  return (
    <div className="rounded-2xl border border-slate-200 bg-white">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center justify-between px-4 py-3 text-sm font-bold text-slate-700"
      >
        <span className="flex items-center gap-2">
          <Info className="w-4 h-4 text-blue-600" /> {t.methodTitle}
        </span>
        <ChevronDown className={`w-4 h-4 transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>
      {open && (
        <div className="px-4 pb-4 text-xs text-slate-600 space-y-3 leading-relaxed">
          {isAr ? (
            <p>
              <strong>التسخين:</strong> الكلفة = V × ΔT ÷ 860 × {PRIX_GAZ} د.ت/kWh (الشريحة الأولى متاع الستاغ). الماء البارد {T_FROIDE} °C؛
              الدوش {T_USAGE.douche} °C (ΔT {T_USAGE.douche - T_FROIDE})، اللافابو {T_USAGE.lavabo} °C (ΔT {T_USAGE.lavabo - T_FROIDE})،
              الكوجينة {T_USAGE.cuisine} °C (ΔT {T_USAGE.cuisine - T_FROIDE}). الفليكسيبل والتواليت: ماء بارد.
            </p>
          ) : (
            <p>
              <strong>Chauffage :</strong> Coût = V × ΔT ÷ 860 × {PRIX_GAZ} DT/kWh (STEG 1ère tranche). Eau froide à {T_FROIDE} °C ;
              douche {T_USAGE.douche} °C (ΔT {T_USAGE.douche - T_FROIDE}), lavabo {T_USAGE.lavabo} °C (ΔT {T_USAGE.lavabo - T_FROIDE}),
              cuisine {T_USAGE.cuisine} °C (ΔT {T_USAGE.cuisine - T_FROIDE}). Flexible et WC : eau froide.
            </p>
          )}
          {isAr ? (
            <p>
              <strong>ماء الصوناد:</strong> V<sub>الثلاثية</sub> = V<sub>النهار</sub> × 90 ÷ 1000. سوم الشريحة اللي توصللها يتطبّق على الكمية
              الكل، ومن بعد نقسمو الكلفة على النهار (÷ 90). هوني: {fmt(r.eauSans.vTrim, 1)} m³ ← {fmt(r.eauAvec.vTrim, 1)} m³ في الثلاثية.
            </p>
          ) : (
            <p>
              <strong>Eau SONEDE :</strong> V<sub>trim</sub> = V<sub>jour</sub> × 90 ÷ 1000. Le tarif de la tranche atteinte s'applique à tout le
              volume, puis le coût est ramené au jour (÷ 90). Ici : {fmt(r.eauSans.vTrim, 1)} m³ → {fmt(r.eauAvec.vTrim, 1)} m³ par trimestre.
            </p>
          )}
          <div className="grid grid-cols-3 sm:grid-cols-6 gap-1.5">
            {SONEDE_TRANCHES.map((tr) => (
              <div
                key={tr.label}
                className={`rounded-lg border px-2 py-1.5 text-center ${
                  tr === r.eauSans.tranche || tr === r.eauAvec.tranche ? 'border-blue-400 bg-blue-50' : 'border-slate-200'
                }`}
              >
                <div className="text-[10px] text-slate-500">{t.tranche(tr.label)}</div>
                <div className="font-bold tabular-nums">{tr.tarif.toFixed(3)}</div>
              </div>
            ))}
          </div>
          {isAr ? (
            <p>
              <strong>التوفير:</strong> في النهار = المجموع بلا − المجموع مع؛ في الشهر = النهار × 30؛ في العام = الشهر × 12.
              <strong> ترجيع الفلوس:</strong> الاستثمار ÷ التوفير في النهار (ولا في الشهر).
            </p>
          ) : (
            <p>
              <strong>Économies :</strong> jour = total sans − total avec ; mois = jour × 30 ; an = mois × 12.
              <strong> Amortissement :</strong> investissement ÷ économie par jour (ou par mois).
            </p>
          )}
        </div>
      )}
    </div>
  );
};

/* ---------- Composant principal ---------- */

export const SavingsCalculator = ({ onSelectPack, onRequestAudit, defaultProfile = 'residentiel' }) => {
  const t = useTxt();
  const [profile, setProfile] = useState(defaultProfile);
  const [hotel, setHotel] = useState(HOTEL_DEFAUTS);
  const [foyer, setFoyer] = useState(FOYER_DEFAUTS);
  const [avance, setAvance] = useState(false);

  const setH = (k) => (v) => setHotel((s) => ({ ...s, [k]: v }));
  const setF = (k) => (v) => setFoyer((s) => ({ ...s, [k]: v }));

  const pack = foyer.personnes <= 4 ? PACKS.appartement : PACKS.maison;
  const packLabel = t.packLabels[pack.id];
  const packId = `${foyer.personnes <= 4 ? 'pack-appartement' : 'pack-maison'}-${foyer.dEcoRobinet === 5 ? '5l' : '4l'}`;

  const rHotel = useMemo(() => simulerHotel(hotel), [hotel]);
  const rFoyer = useMemo(() => simulerFoyer({ ...foyer, prixPack: pack.prix }), [foyer, pack.prix]);

  const demanderAudit = () => {
    const simulation = {
      chambres: hotel.chambres,
      occupation: hotel.occupation,
      investissement: Math.round(rHotel.investissement),
      economieAn: Math.round(rHotel.ecoAn),
      roiJours: Math.round(rHotel.roiJours),
    };
    try {
      sessionStorage.setItem('ecopower_simulation', JSON.stringify(simulation));
    } catch {
      /* stockage indisponible : on continue sans pré-remplissage */
    }
    onRequestAudit?.(simulation);
    document.getElementById('devis-pro')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  const tabClass = (active) =>
    `flex items-center gap-2 px-4 sm:px-5 py-2 rounded-xl text-sm font-bold transition-all ${
      active ? 'bg-white text-blue-800 shadow-sm' : 'text-slate-600 hover:text-slate-900'
    }`;

  return (
    <div className="bg-white rounded-3xl border border-slate-200 shadow-xl p-5 sm:p-8 lg:p-10 max-w-6xl mx-auto my-8">
      <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4 mb-8">
        <div>
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-blue-50 text-blue-800 text-xs font-bold uppercase tracking-wider">
            <Calculator className="w-4 h-4" /> {t.badge}
          </div>
          <h3 className="text-2xl sm:text-3xl font-black text-slate-900 mt-2">{t.title}</h3>
          <p className="text-sm text-slate-500 mt-1">{t.subtitle}</p>
        </div>
        <div className="inline-flex p-1 bg-slate-100 rounded-2xl border border-slate-200 self-start">
          <button type="button" onClick={() => setProfile('residentiel')} className={tabClass(profile === 'residentiel')}>
            <Home className="w-4 h-4" /> {t.tabHome}
          </button>
          <button type="button" onClick={() => setProfile('pro')} className={tabClass(profile === 'pro')}>
            <Building2 className="w-4 h-4" /> {t.tabHotel}
          </button>
        </div>
      </div>

      {profile === 'pro' ? (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 lg:gap-8">
          <div className="lg:col-span-5 space-y-4">
            <Section title={t.hotelSection} icon={Building2}>
              <Slider label={t.rooms} value={hotel.chambres} unit={t.roomsUnit} min={10} max={600} step={5} onChange={setH('chambres')} />
              <Slider label={t.occupancy} value={hotel.occupation} unit="%" min={10} max={100} onChange={setH('occupation')} />
              <Slider
                label={t.perRoom}
                value={hotel.personnesParChambre}
                unit={t.persUnit}
                min={1}
                max={3}
                step={0.1}
                onChange={setH('personnesParChambre')}
                hint={t.hotelHint(fmt(rHotel.clientsJour))}
              />
            </Section>

            <Section title={t.roomEquip} icon={Droplets}>
              <Choice
                label={t.showerSaver(fmt(PRIX_HOTEL.douche, 3))}
                value={hotel.dEcoDouche}
                options={[{ value: 5, label: '5 L/min' }, { value: 7, label: '7 L/min' }]}
                onChange={setH('dEcoDouche')}
              />
              <Choice
                label={t.basinSaver}
                value={hotel.dEcoLavabo}
                options={[
                  { value: 2, label: `2 L/min ${t.black} · ${fmt(PRIX_HOTEL.lavabo[2], 3)} ${t.cur}` },
                  { value: 3, label: `3 L/min ${t.pink} · ${fmt(PRIX_HOTEL.lavabo[3], 3)} ${t.cur}` },
                ]}
                onChange={setH('dEcoLavabo')}
              />
              <Choice
                label={t.flexLabel}
                value={hotel.dEcoFlex}
                options={[
                  { value: 0, label: t.none },
                  { value: 5, label: `5 L/min · ${fmt(PRIX_HOTEL.flex, 3)} ${t.cur}` },
                  { value: 7, label: `7 L/min · ${fmt(PRIX_HOTEL.flex, 3)} ${t.cur}` },
                ]}
                onChange={setH('dEcoFlex')}
              />
              <Choice
                label={t.ecoSac(fmt(hotel.prixEcoSac, 3))}
                value={hotel.ecoSac}
                options={[{ value: false, label: t.no }, { value: true, label: t.yes }]}
                onChange={setH('ecoSac')}
              />
              <div className="flex justify-between text-sm pt-2 border-t border-slate-200">
                <span className="text-slate-600">{t.costRoom}</span>
                <span className="font-bold tabular-nums">{fmt(rHotel.coutChambre, 3)} {t.cur}</span>
              </div>
            </Section>

            <div className="rounded-2xl border border-slate-200">
              <button
                type="button"
                onClick={() => setAvance((a) => !a)}
                className="w-full flex items-center justify-between px-4 py-3 text-sm font-bold text-slate-700"
              >
                {t.advanced}
                <ChevronDown className={`w-4 h-4 transition-transform ${avance ? 'rotate-180' : ''}`} />
              </button>
              {avance && (
                <div className="px-4 pb-4 space-y-4">
                  <Slider label={t.showerFlow} value={hotel.dIniDouche} unit="L/min" min={8} max={25} onChange={setH('dIniDouche')} />
                  <Slider label={t.showerTime} value={hotel.tDouche} unit={t.minClient} min={3} max={20} onChange={setH('tDouche')} />
                  <Slider label={t.basinFlow} value={hotel.dIniLavabo} unit="L/min" min={4} max={20} onChange={setH('dIniLavabo')} />
                  <Slider label={t.basinTime} value={hotel.tLavabo} unit={t.min} min={0.5} max={5} step={0.5} onChange={setH('tLavabo')} />
                  <Slider label={t.basinUses} value={hotel.freqLavabo} unit={t.perClientDay} min={1} max={10} onChange={setH('freqLavabo')} />
                  <Slider label={t.flexTime} value={hotel.tFlex} unit={t.min} min={0.25} max={3} step={0.25} onChange={setH('tFlex')} />
                  <Slider label={t.flexUses} value={hotel.freqFlex} unit={t.perClientDay} min={1} max={8} onChange={setH('freqFlex')} />
                  {hotel.ecoSac && (
                    <Slider label={t.flushes} value={hotel.chassesParClient} unit={t.perClientDay} min={1} max={8} onChange={setH('chassesParClient')} />
                  )}
                  <button
                    type="button"
                    onClick={() => setHotel(HOTEL_DEFAUTS)}
                    className="inline-flex items-center gap-1.5 text-xs font-bold text-blue-700 hover:text-blue-900"
                  >
                    <RotateCcw className="w-3.5 h-3.5" /> {t.reset}
                  </button>
                </div>
              )}
            </div>
          </div>

          <div className="lg:col-span-7">
            <Resultats
              r={rHotel}
              cta={
                <button
                  type="button"
                  onClick={demanderAudit}
                  className="w-full bg-white hover:bg-blue-50 text-blue-950 font-black py-3 px-4 rounded-xl text-sm flex items-center justify-center gap-2 shadow-lg transition"
                >
                  {t.audit} <ArrowRight className="w-4 h-4 rtl:rotate-180" />
                </button>
              }
              extra={
                <div className="rounded-2xl border border-slate-200 p-4 bg-white text-sm flex items-start gap-3">
                  <Wallet className="w-5 h-5 text-blue-600 shrink-0 mt-0.5" />
                  <div className="text-slate-600">
                    {t.hotelInvest(fmt(hotel.chambres), fmt(rHotel.coutChambre, 3), fmt(rHotel.investissement, 3))}
                  </div>
                </div>
              }
            />
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 lg:gap-8">
          <div className="lg:col-span-5 space-y-4">
            <Section title={t.homeSection} icon={Home}>
              <Slider label={t.people} value={foyer.personnes} unit={t.persUnit} min={1} max={10} onChange={setF('personnes')} />
              <Slider label={t.showerTime} value={foyer.tDouche} unit={t.minPers} min={3} max={20} onChange={setF('tDouche')} />
              <Slider label={t.basin} value={foyer.tLavabo} unit={t.minPersDay} min={1} max={10} onChange={setF('tLavabo')} />
              <Slider label={t.kitchen} value={foyer.tCuisine} unit={t.minDay} min={2} max={40} onChange={setF('tCuisine')} />
              <Slider label={t.flushes} value={foyer.chasses} unit={t.perPersDay} min={1} max={8} onChange={setF('chasses')} />
            </Section>

            <Section title={t.installSection} icon={TrendingDown}>
              <Slider
                label={t.showerFlow}
                value={foyer.dIniDouche}
                unit="L/min"
                min={8}
                max={25}
                onChange={setF('dIniDouche')}
                hint={t.showerHint}
              />
              <Slider label={t.tapFlow} value={foyer.dIniRobinet} unit="L/min" min={6} max={20} onChange={setF('dIniRobinet')} />
              <Choice
                label={t.showerReg}
                value={foyer.dEcoDouche}
                options={[{ value: 5, label: '5 L/min' }, { value: 7, label: '7 L/min' }]}
                onChange={setF('dEcoDouche')}
              />
              <Choice
                label={t.tapAerators}
                value={foyer.dEcoRobinet}
                options={[{ value: 4, label: '4 L/min' }, { value: 5, label: '5 L/min' }]}
                onChange={setF('dEcoRobinet')}
              />
              <button
                type="button"
                onClick={() => setFoyer(FOYER_DEFAUTS)}
                className="inline-flex items-center gap-1.5 text-xs font-bold text-blue-700 hover:text-blue-900"
              >
                <RotateCcw className="w-3.5 h-3.5" /> {t.reset}
              </button>
            </Section>
          </div>

          <div className="lg:col-span-7">
            <Resultats
              r={rFoyer}
              cta={
                <div>
                  <div className="text-xs text-blue-200 mb-2 flex items-center gap-1.5">
                    <Timer className="w-3.5 h-3.5" /> {t.recommended} <strong className="text-white">{packLabel}</strong> · {t.refund}
                  </div>
                  <button
                    type="button"
                    onClick={() => onSelectPack?.(packId)}
                    className="w-full bg-white hover:bg-blue-50 text-blue-950 font-black py-3 px-4 rounded-xl text-sm flex items-center justify-center gap-2 shadow-lg transition"
                  >
                    {t.orderPack(packLabel, pack.prix)} <ArrowRight className="w-4 h-4 rtl:rotate-180" />
                  </button>
                </div>
              }
            />
          </div>
        </div>
      )}
    </div>
  );
};
