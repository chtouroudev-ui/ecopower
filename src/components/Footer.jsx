import React from 'react';
import { Droplets, Phone, Mail, MapPin, ShieldCheck, Truck, RefreshCw, Award } from 'lucide-react';
import { useCart } from '../context/CartContext';

// Textes du pied de page : français et darija tunisienne
const TXT = {
  fr: {
    props: [
      ['Garantie 3 Ans', 'Eco-Sac WC garanti à vie'],
      ['Satisfait ou Remboursé', '14 jours pour tester chez vous'],
      ['Livraison Partout en Tunisie', '24 à 48h - Paiement à la livraison'],
      ['Normes ISO & ACS', "Tenue prouvée jusqu'à 25 bars"],
    ],
    about: 'Leader des solutions hydro-économes et de maîtrise énergétique en Tunisie. Nous accompagnons foyers, hôtels, cliniques et entreprises dans la réduction concrète de leurs factures SONEDE & STEG.',
    navTitle: 'Navigation',
    nav: {
      home: 'Accueil',
      particuliers: 'Particuliers & Résidentiel',
      professionnels: 'Professionnels B2B & Hôtels',
      shop: 'Boutique & Packs',
      calculator: "Simulateur d'Économies",
      tracking: 'Suivi de Commande',
      references: 'Références Clients (+100)',
    },
    rangeTitle: 'Gamme Phare',
    range: [
      'Pack Appartement 4L / 5L (78 DT)',
      'Pack Maison / Villa 4L / 5L (129 DT)',
      'Hydro-Économes Delrin 2L à 5L/min',
      'Régulateurs Inox Douche & Flexible',
      'Pommes de Douche Massantes & Anticalcaire',
      'Eco-Sac WC 3L (Garantie à vie)',
      'Ampoules LED à détection PIR',
    ],
    contactTitle: 'Contact & Assistance',
    location: 'Tunis / Sousse / Sfax — Service technique national',
    admin: 'Accès Administration',
    rights: '© 2026 ECOPOWER TUNISIE. Tous droits réservés.',
    certified: "Solutions certifiées ISO 9001 & ACS pour l'hôtellerie, la santé et le résidentiel.",
  },
  ar: {
    props: [
      ['ضمان 3 سنين', 'إيكو-ساك التواليت مضمون مدى الحياة'],
      ['راضي ولا نرجعولك فلوسك', '14 يوم تجرّب في دارك'],
      ['توصيل لكامل تونس', 'من 24 لـ 48 ساعة - الخلاص عند الاستلام'],
      ['معايير ISO و ACS', 'يصمد حتى لـ 25 بار'],
    ],
    about: 'الأول في تونس في حلول توفير الماء والطاقة. نعاونو الديار، النزل، المصحّات والشركات باش ينقّصو بالحق في فواتير الصوناد والستاغ.',
    navTitle: 'الصفحات',
    nav: {
      home: 'الرئيسية',
      particuliers: 'العايلات والديار',
      professionnels: 'المحترفين والنزل',
      shop: 'المتجر والباكات',
      calculator: 'حاسبة التوفير',
      tracking: 'تتبّع الطلبية',
      references: 'مراجعنا (+100)',
    },
    rangeTitle: 'أهم المنتوجات',
    range: [
      'باك الشقة 4L / 5L (78 د.ت)',
      'باك الدار / الفيلا 4L / 5L (129 د.ت)',
      'موفّرات Delrin من 2L لـ 5L/min',
      'منظّمات إينوكس للدوش والفليكسيبل',
      'رؤوس دوش ماساج وضد الكلس',
      'إيكو-ساك التواليت 3L (مضمون مدى الحياة)',
      'لمبات LED بكابتور الحركة',
    ],
    contactTitle: 'الاتصال والمساعدة',
    location: 'تونس / سوسة / صفاقس — خدمة فنية في كامل البلاد',
    admin: 'فضاء الإدارة',
    rights: '© 2026 ECOPOWER TUNISIE. الحقوق الكل محفوظة.',
    certified: 'حلول معتمدة ISO 9001 و ACS للنزل، الصحة والديار.',
  },
};

const PROP_ICONS = [
  { Icon: ShieldCheck, color: 'text-blue-400' },
  { Icon: RefreshCw, color: 'text-sky-400' },
  { Icon: Truck, color: 'text-blue-300' },
  { Icon: Award, color: 'text-blue-400' },
];

const NAV_ORDER = ['home', 'particuliers', 'professionnels', 'shop', 'calculator', 'tracking', 'references'];

export const Footer = ({ setCurrentTab }) => {
  const { language } = useCart();
  const t = TXT[language] || TXT.fr;

  return (
    <footer className="bg-slate-900 text-slate-300 pt-16 pb-12 border-t border-slate-800">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">

        {/* Value props bar */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 pb-12 border-b border-slate-800 text-center md:text-start">
          {PROP_ICONS.map(({ Icon, color }, idx) => (
            <div key={idx} className="flex items-center gap-4 justify-center md:justify-start">
              <div className={`w-12 h-12 rounded-2xl bg-blue-950/80 ${color} flex items-center justify-center shrink-0 border border-blue-800/40`}>
                <Icon className="w-6 h-6" />
              </div>
              <div>
                <h4 className="font-bold text-white text-sm">{t.props[idx][0]}</h4>
                <p className="text-xs text-slate-400">{t.props[idx][1]}</p>
              </div>
            </div>
          ))}
        </div>

        {/* Main Footer Content */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-10 py-12">

          {/* Brand info */}
          <div className="space-y-4">
            <div className="flex items-center gap-2">
              <div className="w-9 h-9 rounded-xl bg-blue-600 flex items-center justify-center text-white shadow-md shadow-blue-500/20">
                <Droplets className="w-5 h-5" />
              </div>
              <span className="font-extrabold text-xl text-white tracking-tight" dir="ltr">ECO<span className="text-blue-400">POWER</span></span>
            </div>
            <p className="text-xs text-slate-400 leading-relaxed">
              {t.about}
            </p>
            <div className="text-xs text-slate-400 font-mono">
              Société ECOGAM SARL • ECEAU-LOGIS
            </div>
          </div>

          {/* Quick links */}
          <div>
            <h5 className="font-bold text-white text-sm uppercase tracking-wider mb-4">{t.navTitle}</h5>
            <ul className="space-y-2 text-xs">
              {NAV_ORDER.map((id) => (
                <li key={id}>
                  <button onClick={() => setCurrentTab(id)} className="hover:text-blue-400 transition">{t.nav[id]}</button>
                </li>
              ))}
            </ul>
          </div>

          {/* Gamme Produits */}
          <div>
            <h5 className="font-bold text-white text-sm uppercase tracking-wider mb-4">{t.rangeTitle}</h5>
            <ul className="space-y-2 text-xs text-slate-400">
              {t.range.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </div>

          {/* Contact */}
          <div>
            <h5 className="font-bold text-white text-sm uppercase tracking-wider mb-4">{t.contactTitle}</h5>
            <ul className="space-y-3 text-xs text-slate-400">
              <li className="flex items-start gap-2.5">
                <MapPin className="w-4 h-4 text-blue-400 shrink-0 mt-0.5" />
                <span>{t.location}</span>
              </li>
              <li className="flex items-center gap-2.5">
                <Phone className="w-4 h-4 text-blue-400 shrink-0" />
                <a href="tel:+21671000000" className="hover:text-white transition" dir="ltr">+216 71 000 000 / +216 98 000 000</a>
              </li>
              <li className="flex items-center gap-2.5">
                <Mail className="w-4 h-4 text-blue-400 shrink-0" />
                <a href="mailto:contact@eco-power.tn" className="hover:text-white transition" dir="ltr">contact@eco-power.tn / eceau-lo@orange.fr</a>
              </li>
              <li className="pt-2">
                <button
                  onClick={() => setCurrentTab('admin')}
                  className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-blue-900 text-slate-300 hover:text-white text-[11px] font-bold transition flex items-center gap-1.5"
                >
                  <span>{t.admin}</span>
                </button>
              </li>
            </ul>
          </div>

        </div>

        {/* Bottom copyright */}
        <div className="pt-8 border-t border-slate-800 text-center text-xs text-slate-500 flex flex-col sm:flex-row justify-between items-center gap-4">
          <p>{t.rights}</p>
          <p className="text-slate-500">
            {t.certified}
          </p>
        </div>

      </div>
    </footer>
  );
};
