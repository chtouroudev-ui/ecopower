import React, { useEffect, useState } from 'react';
import { SavingsCalculator } from '../components/SavingsCalculator';
import { SEO } from '../components/SEO';
import { ReferencesCarousel } from '../components/ReferencesCarousel';
import { 
  Building2, 
  Hotel, 
  Hospital, 
  Award, 
  ShieldCheck, 
  CheckCircle2, 
  Send, 
  FileSpreadsheet, 
  PhoneCall, 
  Mail, 
  Users, 
  Gauge,
  CheckCircle,
  Loader2
} from 'lucide-react';

export const ProfessionnelsPage = () => {
  const [formData, setFormData] = useState({
    company: '',
    contactPerson: '',
    role: '',
    phone: '',
    email: '',
    type: 'hotel',
    roomsCount: '',
    currentWaterBillMonthly: '',
    interest: 'Audit complet & Diagnostic d’amortissement gratuit',
    notes: ''
  });

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [submitError, setSubmitError] = useState('');

  // Pré-remplit la demande avec le résultat du simulateur hôtel
  const applySimulation = (sim) => {
    if (!sim) return;
    setFormData((f) => ({
      ...f,
      type: 'hotel',
      roomsCount: f.roomsCount || String(sim.chambres),
      notes: `Simulation : ${sim.chambres} chambres, occupation ${sim.occupation} %, investissement ${sim.investissement} DT, économie estimée ${sim.economieAn} DT/an, amortissement ${sim.roiJours} jours.${f.notes ? `\n${f.notes}` : ''}`,
    }));
  };

  useEffect(() => {
    try {
      const stored = sessionStorage.getItem('ecopower_simulation');
      if (stored) applySimulation(JSON.parse(stored));
    } catch {
      /* rien à pré-remplir */
    }
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsSubmitting(true);
    setSubmitError('');

    try {
      const res = await fetch('/api/leads', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData)
      });
      if (!res.ok) throw new Error();
      try {
        sessionStorage.removeItem('ecopower_simulation');
      } catch {
        /* ignore */
      }
      setSubmitted(true);
    } catch {
      setSubmitError("Votre demande n'a pas pu être envoyée. Réessayez ou appelez-nous au +216 97 644 988.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="py-10 space-y-16 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
<SEO
  title="Facture SONEDE : économies pour hôtels et cliniques | EcoPower"
  description="Réduisez vos factures SONEDE et STEG dans votre hôtel, clinique ou entreprise. Audit et test de débit gratuits, dispositifs hydro-économes Hostaform."
  path="/professionnels"
/>
      {/* Hero Header */}
      <div className="bg-gradient-to-br from-slate-900 via-brand-950 to-brand-900 text-white rounded-3xl p-8 sm:p-14 shadow-2xl relative overflow-hidden">
        <div className="max-w-3xl space-y-5">
          <div className="inline-flex items-center gap-2 px-3.5 py-1 rounded-full bg-blue-500/20 text-sky-300 text-xs font-bold uppercase tracking-wider border border-blue-500/30">
            <Building2 className="w-4 h-4" />
            <span>Division Hôtellerie, Santé &amp; Entreprises</span>
          </div>
          <h1 className="text-3xl sm:text-5xl font-black font-serif tracking-tight text-white leading-tight">
            Rentabilisez Vos Dépenses d’Eau &amp; d’Énergie en Moins de 90 Jours
          </h1>
          <p className="text-slate-300 text-base sm:text-lg leading-relaxed">
            Leader en Europe et en Tunisie dans le respect des Normes ISO pour l'Hôtellerie, les Cliniques et l'Agro-Alimentaire. Nos dispositifs Hostaform tiennent des pressions jusqu'à 25 bars et résistent aux chocs chlorés.
          </p>

          <div className="pt-2 flex flex-wrap gap-4 text-xs font-bold text-sky-300">
            <span>✅ +60 Hôtels équipés en Tunisie</span>
            <span>•</span>
            <span>✅ +50% des Cliniques Tunisiennes</span>
            <span>•</span>
            <span>✅ Diagnostic &amp; Pose Gratuits</span>
          </div>
        </div>
      </div>

      {/* 3 Pillars for B2B */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
        
        {/* Hotellerie */}
        <div className="bg-white rounded-3xl p-8 border border-slate-200 shadow-sm hover:shadow-xl transition-all space-y-4">
          <div className="w-14 h-14 rounded-2xl bg-skywater-50 text-skywater-600 flex items-center justify-center">
            <Hotel className="w-7 h-7" />
          </div>
          <h3 className="font-extrabold text-xl text-slate-900 font-serif">Milieu Hôtelier</h3>
          <p className="text-xs text-slate-600 leading-relaxed">
            Fort de notre expérience sur <strong>plus de 60 hôtels en Tunisie</strong>, nous assurons un retour sur investissement en <strong>moins de 90 jours</strong> avec un taux d’occupation de 60% à l'année.
          </p>
          <ul className="space-y-2 text-xs text-slate-600 pt-2 border-t border-slate-100">
            <li className="flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-blue-600 shrink-0" />
              <span>Confort de jet inchangé pour vos clients</span>
            </li>
            <li className="flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-blue-600 shrink-0" />
              <span>Baisse drastique de la facture gaz pour chauffer l'eau</span>
            </li>
            <li className="flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-blue-600 shrink-0" />
              <span>Installation en chambre sans interruption de service</span>
            </li>
          </ul>
        </div>

        {/* Cliniques & Hôpitaux */}
        <div className="bg-white rounded-3xl p-8 border border-slate-200 shadow-sm hover:shadow-xl transition-all space-y-4">
          <div className="w-14 h-14 rounded-2xl bg-blue-50 text-blue-600 flex items-center justify-center">
            <Hospital className="w-7 h-7" />
          </div>
          <h3 className="font-extrabold text-xl text-slate-900 font-serif">Santé &amp; Médicalisé</h3>
          <p className="text-xs text-slate-600 leading-relaxed">
            Plus de <strong>50% des cliniques privées en Tunisie</strong> nous ont fait confiance (Clinique Les Oliviers, Al Hakim, Hamda Laouani, Essalem, Le Bardo...).
          </p>
          <ul className="space-y-2 text-xs text-slate-600 pt-2 border-t border-slate-100">
            <li className="flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-blue-600 shrink-0" />
              <span>Attestation de Conformité Sanitaire (ACS)</span>
            </li>
            <li className="flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-blue-600 shrink-0" />
              <span>Matériau Hostaform résistant aux désinfections chlorées</span>
            </li>
            <li className="flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-blue-600 shrink-0" />
              <span>Audit gratuit point par point des zones de soins</span>
            </li>
          </ul>
        </div>

        {/* Comités d'entreprise / CE */}
        <div className="bg-white rounded-3xl p-8 border border-slate-200 shadow-sm hover:shadow-xl transition-all space-y-4">
          <div className="w-14 h-14 rounded-2xl bg-amber-50 text-amber-600 flex items-center justify-center">
            <Users className="w-7 h-7" />
          </div>
          <h3 className="font-extrabold text-xl text-slate-900 font-serif">Packs ECEAU-LOGIS (CE)</h3>
          <p className="text-xs text-slate-600 leading-relaxed">
            Offrez du pouvoir d’achat à vos collaborateurs et nouveaux entrants avec des <strong>Packs personnalisés au logo de votre société</strong> (Banques, Assurances, Grands Comptes).
          </p>
          <ul className="space-y-2 text-xs text-slate-600 pt-2 border-t border-slate-100">
            <li className="flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-blue-600 shrink-0" />
              <span>Cadeau d'entreprise RSE utile et écologique</span>
            </li>
            <li className="flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-blue-600 shrink-0" />
              <span>Personnalisation complète au logo du partenaire</span>
            </li>
            <li className="flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-blue-600 shrink-0" />
              <span>Tarifs comités d’entreprise dégressifs</span>
            </li>
          </ul>
        </div>

      </div>

      {/* Detailed Technical Commitments */}
      <div className="bg-slate-50 border border-slate-200 rounded-3xl p-8 sm:p-12 space-y-8">
        <div className="max-w-2xl">
          <span className="text-xs font-bold text-brand-700 uppercase tracking-wider">
            Notre Méthodologie d’Accompagnement Pro
          </span>
          <h2 className="text-2xl sm:text-3xl font-extrabold text-slate-900 font-serif mt-1">
            Les Engagements de notre Bureau d’Études
          </h2>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
          <div className="p-5 bg-white rounded-2xl border border-slate-200 shadow-2xs">
            <div className="font-black text-brand-800 text-lg mb-1">1. Test de Débit Gratuit</div>
            <p className="text-xs text-slate-600">
              Prise de mesure sur site point par point afin d’évaluer la consommation exacte de chaque robinet et douche.
            </p>
          </div>

          <div className="p-5 bg-white rounded-2xl border border-slate-200 shadow-2xs">
            <div className="font-black text-brand-800 text-lg mb-1">2. Diagnostic d’Amortissement</div>
            <p className="text-xs text-slate-600">
              Calcul précis du retour sur investissement réalisé par nos ingénieurs en France et en Tunisie.
            </p>
          </div>

          <div className="p-5 bg-white rounded-2xl border border-slate-200 shadow-2xs">
            <div className="font-black text-brand-800 text-lg mb-1">3. Pose Spécialisée Offerte</div>
            <p className="text-xs text-slate-600">
              Installation assurée par nos équipes techniques pour garantir une étanchéité parfaite et un calibrage optimal.
            </p>
          </div>

          <div className="p-5 bg-white rounded-2xl border border-slate-200 shadow-2xs">
            <div className="font-black text-brand-800 text-lg mb-1">4. Dossier de Normes ISO</div>
            <p className="text-xs text-slate-600">
              Remise des certifications officielles pour les audits d'organismes de contrôle et labels écologiques.
            </p>
          </div>
        </div>
      </div>

      {/* References Carousel */}
      <ReferencesCarousel />

      {/* B2B Quote & Audit Form (Formulaire pro demandé par Pascal) */}
      <SavingsCalculator defaultProfile="pro" onRequestAudit={applySimulation} />

      <div id="devis-pro" className="bg-white rounded-3xl border border-slate-200 shadow-xl p-8 sm:p-12 max-w-4xl mx-auto">
        <div className="text-center max-w-2xl mx-auto mb-8">
          <span className="px-3 py-1 bg-brand-100 text-brand-800 rounded-full text-xs font-bold uppercase tracking-wider">
            Demande de Renseignement &amp; Audit
          </span>
          <h2 className="text-2xl sm:text-3xl font-extrabold text-slate-900 font-serif mt-2">
            Fiche de Demande Professionnelle
          </h2>
          <p className="text-xs sm:text-sm text-slate-600 mt-2">
            Remplissez ce formulaire pour être mis en relation directe avec notre Service Technico-Commercial (Mme Sonia Douh Fabre &amp; Pascal Fabre).
          </p>
        </div>

        {submitted ? (
          <div className="p-8 bg-blue-50 border border-blue-200 rounded-2xl text-center space-y-4 animate-in fade-in">
            <div className="w-16 h-16 rounded-full bg-blue-600 text-white flex items-center justify-center mx-auto shadow-md">
              <CheckCircle className="w-8 h-8" />
            </div>
            <h3 className="text-xl font-black text-blue-950">Demande Transmise avec Succès !</h3>
            <p className="text-xs sm:text-sm text-blue-800 max-w-md mx-auto">
              Notre équipe technico-commerciale a bien reçu votre demande d'audit pour <strong>{formData.company}</strong>. Un ingénieur vous contactera sous 24h ouvrées.
            </p>
            <button
              onClick={() => setSubmitted(false)}
              className="text-xs font-bold text-blue-700 underline"
            >
              Envoyer une autre demande
            </button>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-6">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">
                  Nom de la Société / Établissement *
                </label>
                <input
                  type="text"
                  required
                  value={formData.company}
                  onChange={(e) => setFormData({ ...formData, company: e.target.value })}
                  placeholder="Ex: Hôtel Palm Beach Djerba"
                  className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 text-sm focus:border-brand-500 focus:ring-2 focus:ring-brand-200 outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">
                  Secteur d'Activité *
                </label>
                <select
                  value={formData.type}
                  onChange={(e) => setFormData({ ...formData, type: e.target.value })}
                  className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 text-sm focus:border-brand-500 focus:ring-2 focus:ring-brand-200 outline-none bg-white"
                >
                  <option value="hotel">Hôtel / Résidence Touristique</option>
                  <option value="clinique">Clinique / Polyclinique / Hôpital</option>
                  <option value="universite">Université / Foyer Universitaire</option>
                  <option value="agroalimentaire">Industrie Agro-Alimentaire</option>
                  <option value="ce_banque">Comité d'Entreprise / Banque / Assurance</option>
                  <option value="autre">Autre structure professionnelle</option>
                </select>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">
                  Personne de Contact *
                </label>
                <input
                  type="text"
                  required
                  value={formData.contactPerson}
                  onChange={(e) => setFormData({ ...formData, contactPerson: e.target.value })}
                  placeholder="M. / Mme Prénom Nom"
                  className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 text-sm focus:border-brand-500 focus:ring-2 focus:ring-brand-200 outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">
                  Fonction / Rôle *
                </label>
                <input
                  type="text"
                  required
                  value={formData.role}
                  onChange={(e) => setFormData({ ...formData, role: e.target.value })}
                  placeholder="Ex: Directeur Technique, DG..."
                  className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 text-sm focus:border-brand-500 focus:ring-2 focus:ring-brand-200 outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">
                  Téléphone Direct *
                </label>
                <input
                  type="tel"
                  required
                  value={formData.phone}
                  onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                  placeholder="+216 7X XXX XXX"
                  className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 text-sm focus:border-brand-500 focus:ring-2 focus:ring-brand-200 outline-none"
                />
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">
                  Adresse Email Pro *
                </label>
                <input
                  type="email"
                  required
                  value={formData.email}
                  onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                  placeholder="direction@hotel.com"
                  className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 text-sm focus:border-brand-500 focus:ring-2 focus:ring-brand-200 outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">
                  Nombre de Chambres / Sanitaires
                </label>
                <input
                  type="number"
                  value={formData.roomsCount}
                  onChange={(e) => setFormData({ ...formData, roomsCount: e.target.value })}
                  placeholder="Ex: 120"
                  className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 text-sm focus:border-brand-500 focus:ring-2 focus:ring-brand-200 outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">
                  Tarif du mètre cube d’eau (TND/m³)
                </label>
                <input
                  type="text"
                  value={formData.currentWaterBillMonthly}
                  onChange={(e) => setFormData({ ...formData, currentWaterBillMonthly: e.target.value })}
                  placeholder="Ex: 3 120 DT"
                  className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 text-sm focus:border-brand-500 focus:ring-2 focus:ring-brand-200 outline-none"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-700 mb-1">
                Objet &amp; Précisions sur votre Demande
              </label>
              <textarea
                rows={3}
                value={formData.notes}
                onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
                placeholder="Décrivez vos besoins spécifiques : test de débit gratuit, devis pour chambres, comités d'entreprise..."
                className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 text-sm focus:border-brand-500 focus:ring-2 focus:ring-brand-200 outline-none"
              />
            </div>

            {submitError && (
              <div role="alert" className="p-3.5 bg-red-50 border border-red-200 text-red-700 rounded-xl text-sm font-semibold">
                {submitError}
              </div>
            )}

            <button
              type="submit"
              disabled={isSubmitting}
              className="w-full bg-brand-700 hover:bg-brand-800 text-white font-black py-4 px-6 rounded-2xl text-base flex items-center justify-center gap-2 shadow-xl shadow-brand-700/20 transition-all hover:scale-[1.01] active:scale-98 disabled:opacity-70"
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin" />
                  <span>Envoi de votre demande...</span>
                </>
              ) : (
                <>
                  <Send className="w-5 h-5" />
                  <span>Envoyer la Demande d’Audit &amp; Devis Gratuit</span>
                </>
              )}
            </button>

            <div className="text-center text-[11px] text-slate-600">
              🔒 Vos données restent strictement confidentielles au bureau d'études EcoPower / ECOGAM.
            </div>
          </form>
        )}
      </div>

    </div>
  );
};
