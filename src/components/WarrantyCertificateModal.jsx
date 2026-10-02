import React, { useState, useEffect } from 'react';
import { X, Printer, ShieldCheck, Award, Droplets, CheckCircle, Loader2 } from 'lucide-react';

export const WarrantyCertificateModal = ({ certificate: initialCert, orderId, onClose }) => {
  const [certificate, setCertificate] = useState(initialCert || null);
  const [loading, setLoading] = useState(!initialCert && !!orderId);

  useEffect(() => {
    if (!initialCert && orderId) {
      setLoading(true);
      fetch(`/api/certificate/${orderId}`)
        .then(res => res.json())
        .then(data => {
          setCertificate(data);
        })
        .catch(console.error)
        .finally(() => setLoading(false));
    }
  }, [initialCert, orderId]);

  if (!certificate && !loading) return null;

  const handlePrint = () => {
    window.print();
  };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/80 backdrop-blur-xs flex items-center justify-center p-4">
      
      {/* Container */}
      <div className="bg-white rounded-3xl max-w-3xl w-full shadow-2xl border border-slate-200 overflow-hidden my-6">
        
        {/* Modal Controls (Not printed) */}
        <div className="p-4 bg-slate-100 border-b border-slate-200 flex items-center justify-between no-print">
          <div className="flex items-center gap-2 text-xs font-bold text-slate-700">
            <Award className="w-4 h-4 text-blue-600" />
            <span>Certificat Officiel de Garantie &amp; Conformité EcoPower</span>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={handlePrint}
              className="flex items-center gap-1.5 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-xs font-bold shadow-xs transition"
            >
              <Printer className="w-4 h-4" />
              <span>Imprimer le Certificat</span>
            </button>
            <button
              onClick={onClose}
              className="p-2 text-slate-500 hover:text-slate-800 rounded-xl hover:bg-slate-200 transition"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {loading ? (
          <div className="p-16 text-center">
            <Loader2 className="w-8 h-8 text-blue-600 animate-spin mx-auto mb-2" />
            <p className="text-xs text-slate-500 font-medium">Chargement du certificat officiel...</p>
          </div>
        ) : (
          /* Printable Certificate Content */
          <div className="p-8 sm:p-12 bg-[#fffdfa] border-8 border-blue-900/10 m-2 sm:m-4 rounded-2xl relative print:m-0 print:border-4 print:p-8">
            
            {/* Watermark Logo */}
            <div className="absolute inset-0 flex items-center justify-center opacity-4 pointer-events-none">
              <Droplets className="w-96 h-96 text-blue-900" />
            </div>

            {/* Top Certificate Header */}
            <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center pb-6 border-b-2 border-blue-800/20 gap-4">
              <div className="flex items-center gap-3">
                <div className="w-12 h-12 rounded-2xl bg-blue-900 text-white flex items-center justify-center shadow-md">
                  <Droplets className="w-7 h-7 text-sky-400" />
                </div>
                <div>
                  <h1 className="text-2xl font-black tracking-tight text-blue-950 font-serif">
                    ECO<span className="text-sky-600">POWER</span> TUNISIE
                  </h1>
                  <p className="text-xs uppercase font-extrabold tracking-widest text-slate-500">
                    ECOGAM SARL • ECEAU-LOGIS
                  </p>
                </div>
              </div>

              <div className="text-left sm:text-right border-l-2 sm:border-l-0 sm:border-r-0 border-blue-600 pl-3 sm:pl-0">
                <span className="text-[10px] uppercase font-bold text-slate-400 tracking-wider block">Numéro de Certificat</span>
                <span className="font-mono text-base font-extrabold text-blue-900">
                  {certificate.certificateSerial}
                </span>
                <span className="text-[10px] text-slate-500 block">
                  Délivré le : {new Date(certificate.issueDate).toLocaleDateString('fr-FR')}
                </span>
              </div>
            </div>

            {/* Certificate Title */}
            <div className="py-6 text-center space-y-1">
              <span className="text-xs uppercase font-extrabold tracking-widest text-blue-800 bg-blue-100/70 px-4 py-1 rounded-full">
                Document d'Agrément Technique &amp; Garantie Constructeur
              </span>
              <h2 className="text-2xl sm:text-3xl font-black text-slate-900 font-serif pt-2">
                CERTIFICAT DE CONFORMITÉ &amp; GARANTIE 3 ANS
              </h2>
              <p className="text-xs text-slate-500 max-w-xl mx-auto">
                Ce certificat atteste que les équipements hydro-économes ci-dessous ont été contrôlés et satisfont aux exigences des normes internationales ISO 9001 et sanitaires ACS.
              </p>
            </div>

            {/* Beneficiary Info Box */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 p-4 bg-slate-50 rounded-2xl border border-slate-200 text-xs mb-6">
              <div>
                <span className="text-slate-400 text-[10px] uppercase font-bold">Bénéficiaire / Propriétaire :</span>
                <div className="font-extrabold text-slate-900 text-sm">{certificate.customerName}</div>
                <div className="text-slate-600">{certificate.customerAddress}</div>
              </div>
              <div>
                <span className="text-slate-400 text-[10px] uppercase font-bold">Coordonnées :</span>
                <div className="font-mono text-slate-800">{certificate.customerPhone}</div>
                <div className="text-slate-600">Réf. Commande : <strong>{certificate.orderId}</strong></div>
              </div>
            </div>

            {/* Products and Serial Numbers Table */}
            <div className="mb-6">
              <h3 className="text-xs uppercase font-extrabold tracking-wider text-slate-700 mb-2">
                Articles Couverts &amp; Numéros de Série Gravés :
              </h3>
              <div className="border border-slate-200 rounded-xl overflow-hidden bg-white text-xs">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="bg-slate-100 text-slate-700 font-bold border-b border-slate-200">
                      <th className="p-2.5">Désignation du Produit</th>
                      <th className="p-2.5 text-center">Qté</th>
                      <th className="p-2.5">Numéro(s) de Série Gravé(s)</th>
                      <th className="p-2.5 text-right">Durée Garantie</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {certificate.items?.map((item, idx) => (
                      <tr key={idx} className="hover:bg-slate-50/50">
                        <td className="p-2.5 font-bold text-slate-900">{item.name}</td>
                        <td className="p-2.5 text-center font-mono font-semibold">{item.quantity}</td>
                        <td className="p-2.5 font-mono text-blue-900 font-semibold text-[11px]">
                          {item.serials?.join(', ') || 'SN-ECO-STD-2026'}
                        </td>
                        <td className="p-2.5 text-right font-bold text-blue-700">
                          {item.name.toLowerCase().includes('sac') ? 'À VIE' : '3 ANS'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Norms & Specifications */}
            <div className="p-4 bg-blue-50/50 rounded-2xl border border-blue-200/60 text-xs space-y-2 mb-8">
              <div className="flex items-center gap-2 font-bold text-slate-800">
                <ShieldCheck className="w-4 h-4 text-blue-600" />
                <span>Caractéristiques &amp; Conformité aux Normes :</span>
              </div>
              <ul className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-slate-600 text-[11px]">
                <li className="flex items-start gap-1.5">
                  <CheckCircle className="w-3.5 h-3.5 text-blue-600 shrink-0 mt-0.5" />
                  <span>Résistance éprouvée jusqu'à <strong>25 Bars</strong> de pression</span>
                </li>
                <li className="flex items-start gap-1.5">
                  <CheckCircle className="w-3.5 h-3.5 text-blue-600 shrink-0 mt-0.5" />
                  <span>Matériau breveté <strong>Delrin / Hostaform</strong> anticalcaire</span>
                </li>
                <li className="flex items-start gap-1.5">
                  <CheckCircle className="w-3.5 h-3.5 text-blue-600 shrink-0 mt-0.5" />
                  <span>Conforme ACS (Attestation de Conformité Sanitaire)</span>
                </li>
                <li className="flex items-start gap-1.5">
                  <CheckCircle className="w-3.5 h-3.5 text-blue-600 shrink-0 mt-0.5" />
                  <span>Éligible aux audits de contrôle <strong>ISO 9001</strong></span>
                </li>
              </ul>
            </div>

            {/* Official Stamp & Signatures */}
            <div className="pt-6 border-t border-slate-200 flex flex-col sm:flex-row justify-between items-end gap-6">
              <div className="text-[11px] text-slate-500 space-y-1">
                <p><strong>ECOGAM SARL / ECOPOWER TUNISIE</strong></p>
                <p>Service Qualité &amp; Suivi des Installations</p>
                <p>Contact technique : eceau-lo@orange.fr / +216 98 000 000</p>
              </div>

              <div className="text-center p-3 border-2 border-dashed border-blue-600/40 rounded-2xl bg-white w-48 shadow-2xs">
                <div className="w-8 h-8 mx-auto rounded-full bg-blue-100 flex items-center justify-center text-blue-800 mb-1">
                  <Award className="w-5 h-5 text-blue-700" />
                </div>
                <span className="text-[9px] font-black uppercase text-blue-900 block leading-tight">
                  CERTIFIÉ CONFORME
                </span>
                <span className="text-[8px] text-slate-500 block">Direction Technique EcoPower</span>
                <span className="text-[8px] font-mono text-blue-700 font-bold block mt-1">VISA QUALITÉ VALIDE</span>
              </div>
            </div>

          </div>
        )}

      </div>
    </div>
  );
};
