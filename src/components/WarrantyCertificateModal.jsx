import React from 'react';
import { X, Printer, ShieldCheck, Award, Droplets, CheckCircle, QrCode } from 'lucide-react';

export const WarrantyCertificateModal = ({ certificate, onClose }) => {
  if (!certificate) return null;

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
            <Award className="w-4 h-4 text-brand-600" />
            <span>Certificat Officiel de Garantie &amp; Conformité EcoPower</span>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={handlePrint}
              className="flex items-center gap-1.5 px-4 py-2 bg-brand-700 hover:bg-brand-800 text-white rounded-xl text-xs font-bold shadow-xs transition"
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

        {/* Printable Certificate Content */}
        <div className="p-8 sm:p-12 bg-[#fffdfa] border-8 border-brand-900/10 m-2 sm:m-4 rounded-2xl relative print:m-0 print:border-4 print:p-8">
          
          {/* Watermark Logo */}
          <div className="absolute inset-0 flex items-center justify-center opacity-4 pointer-events-none">
            <Droplets className="w-96 h-96 text-brand-900" />
          </div>

          {/* Top Certificate Header */}
          <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center pb-6 border-b-2 border-brand-800/20 gap-4">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 rounded-2xl bg-brand-900 text-white flex items-center justify-center shadow-md">
                <Droplets className="w-7 h-7 text-skywater-400" />
              </div>
              <div>
                <h1 className="text-2xl font-black tracking-tight text-brand-950 font-serif">
                  ECO<span className="text-skywater-600">POWER</span> TUNISIE
                </h1>
                <p className="text-xs uppercase font-extrabold tracking-widest text-slate-500">
                  ECOGAM SARL • ECEAU-LOGIS
                </p>
              </div>
            </div>

            <div className="text-left sm:text-right">
              <span className="px-3 py-1 bg-amber-100 text-amber-900 rounded-full text-[10px] font-black tracking-wider uppercase border border-amber-300">
                Certificat d'Authenticité
              </span>
              <div className="mt-1 font-mono font-bold text-sm text-slate-800">
                {certificate.certificateSerial}
              </div>
              <div className="text-[11px] text-slate-500">
                Délivré le : {new Date(certificate.issueDate || Date.now()).toLocaleDateString('fr-FR')}
              </div>
            </div>
          </div>

          {/* Title */}
          <div className="text-center my-6">
            <h2 className="text-xl sm:text-2xl font-black text-brand-900 uppercase tracking-wide font-serif">
              Certificat de Garantie &amp; de Conformité Technique
            </h2>
            <p className="text-xs text-slate-600 mt-1 max-w-lg mx-auto">
              Atteste que les dispositifs hydro-économes mentionnés ci-dessous sont certifiés conformes aux normes européennes et internationales ISO avec garantie pièces et fonctionnement.
            </p>
          </div>

          {/* Beneficiary Info */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 p-4 rounded-xl bg-white border border-slate-200 text-xs shadow-2xs mb-6">
            <div>
              <span className="text-slate-400 block text-[10px] uppercase font-bold">Bénéficiaire / Client :</span>
              <strong className="text-slate-900 text-sm">{certificate.customerName}</strong>
              <div className="text-slate-600 mt-0.5">{certificate.customerAddress}</div>
            </div>
            <div>
              <span className="text-slate-400 block text-[10px] uppercase font-bold">Contact Téléphonique :</span>
              <strong className="text-slate-900">{certificate.customerPhone}</strong>
              <div className="text-slate-600 mt-0.5">Commande Réf : #{certificate.orderId}</div>
            </div>
          </div>

          {/* Items & Serial Numbers Table */}
          <div className="mb-6">
            <h3 className="text-xs font-bold text-slate-800 uppercase tracking-wider mb-2">
              Désignation des Articles &amp; Numéros de Série Uniques :
            </h3>
            <div className="border border-slate-200 rounded-xl overflow-hidden bg-white text-xs">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="bg-slate-100 text-slate-700 font-bold border-b border-slate-200">
                    <th className="p-2.5">Article / Pack</th>
                    <th className="p-2.5 text-center">Quantité</th>
                    <th className="p-2.5">Numéro(s) de Série Gravé(s)</th>
                    <th className="p-2.5 text-right">Garantie</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {certificate.items?.map((item, idx) => (
                    <tr key={idx} className="hover:bg-slate-50/50">
                      <td className="p-2.5 font-semibold text-slate-900">{item.name}</td>
                      <td className="p-2.5 text-center font-bold">{item.quantity}</td>
                      <td className="p-2.5 font-mono text-[11px] text-brand-800">
                        {item.serials && item.serials.length > 0
                          ? item.serials.join(', ')
                          : `SN-ECO-${Date.now().toString().slice(-6)}`}
                      </td>
                      <td className="p-2.5 text-right font-bold text-emerald-700">
                        {item.name.toLowerCase().includes('sac') ? 'À VIE' : '3 ANS'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Technical Specifications */}
          <div className="p-4 rounded-xl bg-slate-50 border border-slate-200/80 text-[11px] text-slate-600 space-y-1.5 mb-6">
            <div className="flex items-center gap-2 font-bold text-slate-800">
              <ShieldCheck className="w-4 h-4 text-emerald-600" />
              <span>Caractéristiques &amp; Conformité aux Normes :</span>
            </div>
            <p>• <strong>Revêtement Exclusif Breveté :</strong> HOSTAFORM ou DELRIN (résistance au tartre et au calcaire).</p>
            <p>• <strong>Résistance Mécanique :</strong> Tenue garantie sous des pressions jusqu'à 25 Bars et aux chocs thermiques/chlorés.</p>
            <p>• <strong>Normes Sanitaires :</strong> Attestation de Conformité Sanitaire (ACS) &amp; Conformité ISO 9001 / ISO 14001.</p>
          </div>

          {/* Signatures & Seal */}
          <div className="pt-6 border-t-2 border-brand-800/20 flex flex-col sm:flex-row justify-between items-center gap-6">
            
            {/* Stamp simulation */}
            <div className="border-2 border-dashed border-brand-700/60 p-3 rounded-2xl flex items-center gap-3 text-[11px] bg-brand-50/50">
              <Award className="w-8 h-8 text-brand-700 shrink-0" />
              <div>
                <strong className="block text-brand-900 uppercase font-black">ECOPOWER TUNISIE SARL</strong>
                <span className="text-slate-600">Tampon de Contrôle Qualité &amp; Sortie Usine</span>
              </div>
            </div>

            {/* Signature */}
            <div className="text-center sm:text-right">
              <span className="text-[10px] text-slate-400 uppercase font-bold block mb-1">Direction Technique &amp; Qualité</span>
              <div className="font-serif italic font-bold text-lg text-brand-950">Pascal FABRE</div>
              <span className="text-[10px] text-slate-500">Service Technico-Commercial EcoPower</span>
            </div>

          </div>

        </div>

      </div>
    </div>
  );
};
