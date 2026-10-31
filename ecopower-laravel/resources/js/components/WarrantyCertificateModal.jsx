import React, { useState, useEffect } from 'react';
import { X, Printer, Download, ShieldCheck, Award, Droplets, CheckCircle, Loader2, FileText, Package } from 'lucide-react';

// Dedicated high-resolution printable document generator
export function printCertificateDirectly(certificate) {
  if (!certificate) return;

  const rawSubtotal = certificate.subtotal || certificate.items?.reduce((sum, item) => sum + (parseFloat(item.price) || 0) * (item.quantity || 1), 0) || 0;
  const itemsCount = certificate.items?.length || 1;
  const defaultItemPrice = rawSubtotal > 0 ? (rawSubtotal / itemsCount) : 78.0;
  const deliveryFee = certificate.deliveryFee !== undefined ? parseFloat(certificate.deliveryFee) : 8.0;
  const discount = parseFloat(certificate.discount) || 0;
  const isPickup = certificate.deliveryMethod === 'pickup';
  const subtotal = rawSubtotal > 0 ? rawSubtotal : (defaultItemPrice * itemsCount);
  const total = certificate.total ? parseFloat(certificate.total) : (subtotal - discount + deliveryFee);
  const certNumber = certificate.certificateSerial || `CERT-2026-${certificate.orderId}`;
  const issueDate = certificate.issueDate ? new Date(certificate.issueDate).toLocaleDateString('fr-FR') : new Date().toLocaleDateString('fr-FR');

  const itemsRows = (certificate.items || []).map(item => {
    const p = (item.price && parseFloat(item.price) > 0) ? parseFloat(item.price) : (item.name?.toLowerCase().includes('maison') ? 129.0 : 78.0);
    const q = item.quantity || 1;
    const t = p * q;
    return `
      <tr>
        <td style="padding: 7px 10px; border-bottom: 1px solid #e2e8f0; font-weight: 600; color: #0f172a;">${item.name}</td>
        <td style="padding: 7px 10px; border-bottom: 1px solid #e2e8f0; text-align: center; font-family: monospace;">${q}</td>
        <td style="padding: 7px 10px; border-bottom: 1px solid #e2e8f0; text-align: right; font-family: monospace;">${p.toFixed(2)} DT</td>
        <td style="padding: 7px 10px; border-bottom: 1px solid #e2e8f0; text-align: right; font-family: monospace; font-weight: 700; color: #1e3a8a;">${t.toFixed(2)} DT</td>
      </tr>
    `;
  }).join('');

  const serialsRows = (certificate.items || []).map((item, idx) => {
    const snList = item.serials && item.serials.length > 0 ? item.serials.join(', ') : `SN-ECO-2026-${certificate.orderId}-${idx + 1}`;
    const duration = item.name?.toLowerCase().includes('sac') ? 'À VIE' : '3 ANS';
    return `
      <tr>
        <td style="padding: 7px 10px; border-bottom: 1px solid #e2e8f0; font-weight: 700; color: #0f172a;">${item.name}</td>
        <td style="padding: 7px 10px; border-bottom: 1px solid #e2e8f0; text-align: center; font-family: monospace;">${item.quantity || 1}</td>
        <td style="padding: 7px 10px; border-bottom: 1px solid #e2e8f0; font-family: monospace; color: #1d4ed8; font-weight: 700; font-size: 11px;">${snList}</td>
        <td style="padding: 7px 10px; border-bottom: 1px solid #e2e8f0; text-align: right; font-weight: 800; color: #1e3a8a;">${duration}</td>
      </tr>
    `;
  }).join('');

  const html = `<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <title>Facture_Garantie_${certNumber}</title>
  <style>
    @page {
      size: A4 portrait;
      margin: 10mm 12mm;
    }
    * { box-sizing: border-box; -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      color: #1e293b;
      margin: 0;
      padding: 0;
      background: #ffffff;
      font-size: 11.5px;
      line-height: 1.35;
    }
    .cert-container {
      border: 3px double #1e3a8a;
      padding: 22px 26px;
      border-radius: 6px;
      background: #ffffff;
    }
    .header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      border-bottom: 2px solid #1e3a8a;
      padding-bottom: 12px;
    }
    .brand {
      font-family: Georgia, serif;
      font-size: 24px;
      font-weight: 900;
      color: #0f172a;
      letter-spacing: -0.5px;
    }
    .brand span { color: #2563eb; }
    .sub-brand {
      font-size: 8.5px;
      font-weight: 800;
      letter-spacing: 1.5px;
      color: #64748b;
      text-transform: uppercase;
      margin-top: 2px;
    }
    .cert-ref { text-align: right; }
    .cert-serial {
      font-family: monospace;
      font-size: 14px;
      font-weight: 800;
      color: #1e3a8a;
    }
    .title-box {
      text-align: center;
      margin: 14px 0 12px;
    }
    .badge {
      display: inline-block;
      background: #eff6ff;
      border: 1px solid #bfdbfe;
      color: #1e3a8a;
      font-size: 9.5px;
      font-weight: 800;
      text-transform: uppercase;
      letter-spacing: 1.5px;
      padding: 2px 12px;
      border-radius: 20px;
    }
    .main-title {
      font-family: Georgia, serif;
      font-size: 18px;
      font-weight: 900;
      color: #0f172a;
      margin: 5px 0 2px;
    }
    .sub-title {
      font-size: 10.5px;
      color: #64748b;
    }
    .client-box {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
      background: #f8fafc;
      border: 1px solid #e2e8f0;
      border-radius: 6px;
      padding: 10px 14px;
      margin-bottom: 14px;
      font-size: 11px;
    }
    .section-label {
      font-size: 9.5px;
      text-transform: uppercase;
      font-weight: 800;
      color: #64748b;
      letter-spacing: 0.5px;
      margin-bottom: 2px;
    }
    .section-title {
      font-size: 10.5px;
      font-weight: 800;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      color: #0f172a;
      margin: 12px 0 5px;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      border: 1px solid #e2e8f0;
      border-radius: 4px;
      margin-bottom: 10px;
    }
    th {
      background: #f1f5f9;
      color: #334155;
      font-weight: 700;
      font-size: 9.5px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      padding: 6px 10px;
      border-bottom: 1px solid #cbd5e1;
      text-align: left;
    }
    .total-row {
      background: #eff6ff !important;
      border-top: 2px solid #93c5fd;
      font-weight: 900;
      color: #1e3a8a;
      font-size: 12.5px;
    }
    .specs-box {
      background: #f8fafc;
      border: 1px solid #cbd5e1;
      border-radius: 6px;
      padding: 9px 12px;
      margin: 10px 0;
      font-size: 10px;
    }
    .specs-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 5px;
      color: #475569;
      margin-top: 3px;
    }
    .footer {
      display: flex;
      justify-content: space-between;
      align-items: flex-end;
      border-top: 1px solid #cbd5e1;
      padding-top: 10px;
      margin-top: 10px;
      font-size: 9px;
      color: #64748b;
    }
    .stamp-box {
      border: 2px dashed #2563eb;
      border-radius: 6px;
      padding: 6px 12px;
      text-align: center;
      background: #ffffff;
      width: 160px;
    }
    .stamp-title {
      font-size: 8.5px;
      font-weight: 900;
      color: #1e3a8a;
      text-transform: uppercase;
      display: block;
    }
  </style>
</head>
<body>
  <div class="cert-container">
    <div class="header">
      <div>
        <div class="brand">ECO<span>POWER</span> TUNISIE</div>
        <div class="sub-brand">ECOGAM SARL • ECEAU-LOGIS • HAUTE ÉCONOMIE D'EAU</div>
      </div>
      <div class="cert-ref">
        <div class="section-label">N° Certificat & Facture</div>
        <div class="cert-serial">${certNumber}</div>
        <div style="font-size: 9.5px; color: #64748b; margin-top: 2px;">Date : ${issueDate}</div>
      </div>
    </div>

    <div class="title-box">
      <span class="badge">Document d'Agrément Technique & Facture d'Achat</span>
      <div class="main-title">CERTIFICAT DE GARANTIE 3 ANS & FACTURE</div>
      <div class="sub-title">Attestation officielle de conformité aux normes ISO 9001 et aux attestations sanitaires ACS</div>
    </div>

    <div class="client-box">
      <div>
        <div class="section-label">Client / Bénéficiaire :</div>
        <div style="font-size: 12.5px; font-weight: 800; color: #0f172a;">${certificate.customerName || 'Client Particulier'}</div>
        <div style="color: #475569; margin-top: 2px;">${certificate.customerAddress || 'Tunisie'}</div>
      </div>
      <div>
        <div class="section-label">Coordonnées & Référence :</div>
        <div style="font-family: monospace; font-size: 11.5px; font-weight: 700; color: #0f172a;">${certificate.customerPhone || '+216 -- --- ---'}</div>
        <div style="color: #475569; margin-top: 2px;">Réf. Commande : <strong>${certificate.orderId}</strong></div>
      </div>
    </div>

    <div class="section-title">1. Détail de la Facture d'Achat :</div>
    <table>
      <thead>
        <tr>
          <th>Désignation du Produit</th>
          <th style="text-align: center;">Qté</th>
          <th style="text-align: right;">Prix Unit.</th>
          <th style="text-align: right;">Total TTC</th>
        </tr>
      </thead>
      <tbody>
        ${itemsRows}
        ${discount > 0 ? `<tr style="background: #f8fafc;">
          <td colspan="3" style="padding: 6px 10px; color: #1d4ed8; font-weight: 500;">Remise retrait au local (-10%)</td>
          <td style="padding: 6px 10px; text-align: right; font-family: monospace; font-weight: 700; color: #1d4ed8;">-${discount.toFixed(2)} DT</td>
        </tr>` : ''}
        <tr style="background: #f8fafc;">
          <td colspan="3" style="padding: 6px 10px; color: #64748b; font-weight: 500;">${isPickup ? 'Retrait au local (sans frais de livraison)' : 'Frais de livraison express à domicile partout en Tunisie'}</td>
          <td style="padding: 6px 10px; text-align: right; font-family: monospace; font-weight: 700;">${deliveryFee.toFixed(2)} DT</td>
        </tr>
        <tr class="total-row">
          <td colspan="3" style="padding: 8px 10px; text-transform: uppercase;">MONTANT TOTAL NET À PAYER (TTC)</td>
          <td style="padding: 8px 10px; text-align: right; font-family: monospace;">${total.toFixed(2)} DT</td>
        </tr>
      </tbody>
    </table>

    <div class="section-title">2. Matériels Couverts & Numéros de Série Gravés :</div>
    <table>
      <thead>
        <tr>
          <th>Article</th>
          <th style="text-align: center;">Qté</th>
          <th>Numéro(s) de Série Gravé(s)</th>
          <th style="text-align: right;">Durée Garantie</th>
        </tr>
      </thead>
      <tbody>
        ${serialsRows}
      </tbody>
    </table>

    <div class="specs-box">
      <div style="font-weight: 800; color: #1e3a8a; text-transform: uppercase; font-size: 9.5px; letter-spacing: 0.5px;">
        Spécifications Techniques & Homologations Officielles :
      </div>
      <div class="specs-grid">
        <div>✓ Résistance éprouvée sous haute pression jusqu'à <strong>25 Bars</strong></div>
        <div>✓ Matériau de précision <strong>Delrin / Hostaform</strong> antitartre & anticalcaire</div>
        <div>✓ Certifié <strong>ACS</strong> (Attestation de Conformité Sanitaire)</div>
        <div>✓ Conforme aux exigences de management de la qualité <strong>ISO 9001</strong></div>
      </div>
    </div>

    <div class="footer">
      <div>
        <div style="font-weight: 800; color: #0f172a;">ECOGAM SARL / ECOPOWER TUNISIE</div>
        <div>Direction Technique & Service Qualité Pascal FABRE</div>
        <div>Support Client : +216 97 644 988 • eceau-lo@orange.fr • www.ecopower.tn</div>
      </div>

      <div class="stamp-box">
        <span class="stamp-title">CERTIFIÉ CONFORME</span>
        <span style="font-size: 7.5px; color: #64748b; display: block;">Visa Qualité Technique</span>
        <span style="font-size: 8px; font-family: monospace; font-weight: 800; color: #2563eb; display: block; margin-top: 2px;">GARANTIE VALIDÉE</span>
      </div>
    </div>
  </div>
</body>
</html>`;

  try {
    let iframe = document.getElementById('ecopower-print-iframe');
    if (!iframe) {
      iframe = document.createElement('iframe');
      iframe.id = 'ecopower-print-iframe';
      iframe.style.position = 'fixed';
      iframe.style.right = '0';
      iframe.style.bottom = '0';
      iframe.style.width = '0';
      iframe.style.height = '0';
      iframe.style.border = '0';
      document.body.appendChild(iframe);
    }

    const doc = iframe.contentWindow.document;
    doc.open();
    doc.write(html);
    doc.close();

    setTimeout(() => {
      try {
        iframe.contentWindow.focus();
        iframe.contentWindow.print();
      } catch (err) {
        console.warn('Iframe print error, falling back:', err);
        fallbackPrint(html, certNumber);
      }
    }, 250);
  } catch (err) {
    fallbackPrint(html, certNumber);
  }
}

function fallbackPrint(html, certNumber) {
  const printWindow = window.open('', '_blank', 'width=900,height=800');
  if (printWindow) {
    printWindow.document.open();
    printWindow.document.write(html);
    printWindow.document.close();
    setTimeout(() => {
      printWindow.focus();
      printWindow.print();
    }, 300);
  } else {
    const prevTitle = document.title;
    document.title = `Facture_Garantie_${certNumber}`;
    window.print();
    setTimeout(() => { document.title = prevTitle; }, 1000);
  }
}

export const WarrantyCertificateModal = ({ certificate: initialCert, orderId, onClose }) => {
  const [certificate, setCertificate] = useState(initialCert || null);
  const [loading, setLoading] = useState(!initialCert && !!orderId);

  useEffect(() => {
    if (!initialCert && orderId) {
      setLoading(true);
      fetch(`/api/certificate/${orderId}`)
        .then(res => res.json())
        .then(data => setCertificate(data))
        .catch(console.error)
        .finally(() => setLoading(false));
    }
  }, [initialCert, orderId]);

  // Close on Escape key
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && onClose) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  if (!certificate && !loading) return null;

  const handlePrint = () => {
    if (certificate) {
      printCertificateDirectly(certificate);
    }
  };

  // Compute realistic pricing
  const rawSubtotal = certificate?.subtotal || certificate?.items?.reduce((sum, item) => sum + (parseFloat(item.price) || 0) * (item.quantity || 1), 0) || 0;
  const itemsCount = certificate?.items?.length || 1;
  const defaultItemPrice = rawSubtotal > 0 ? (rawSubtotal / itemsCount) : 78.0;

  const deliveryFee = certificate?.deliveryFee !== undefined ? parseFloat(certificate.deliveryFee) : 8.0;
  const discount = parseFloat(certificate?.discount) || 0;
  const isPickup = certificate?.deliveryMethod === 'pickup';
  const subtotal = rawSubtotal > 0 ? rawSubtotal : (defaultItemPrice * itemsCount);
  const total = certificate?.total ? parseFloat(certificate.total) : (subtotal - discount + deliveryFee);

  return (
    <div 
      className="certificate-modal-overlay fixed inset-0 z-50 overflow-y-auto bg-slate-900/80 backdrop-blur-sm flex items-center justify-center p-3 sm:p-4"
      onClick={onClose}
    >
      {/* Outer Container (stops propagation so clicking inside does not close) */}
      <div 
        className="certificate-modal-container bg-white rounded-3xl max-w-3xl w-full shadow-2xl border border-slate-200 overflow-hidden my-4 sm:my-6 animate-in zoom-in-95 duration-150"
        onClick={(e) => e.stopPropagation()}
      >

        {/* Modal Controls Bar — hidden when printing */}
        <div className="p-3.5 sm:p-4 bg-slate-100 border-b border-slate-200 flex items-center justify-between no-print gap-2">
          <div className="flex items-center gap-2 text-xs font-bold text-slate-700 truncate">
            <Award className="w-4 h-4 text-blue-600 shrink-0" />
            <span className="truncate">Certificat de Garantie & Facture Officielle — EcoPower</span>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <button
              onClick={handlePrint}
              className="flex items-center gap-1.5 px-3 sm:px-4 py-2 bg-blue-600 hover:bg-blue-700 active:bg-blue-800 text-white rounded-xl text-xs font-bold shadow-sm transition"
              title="Lancer l'impression ou enregistrer en PDF"
            >
              <Printer className="w-4 h-4" />
              <span>Imprimer</span>
            </button>
            <button
              onClick={handlePrint}
              className="flex items-center gap-1.5 px-3 sm:px-4 py-2 bg-slate-800 hover:bg-slate-900 active:bg-black text-white rounded-xl text-xs font-bold shadow-sm transition"
              title="Télécharger la facture au format PDF"
            >
              <Download className="w-4 h-4" />
              <span>Télécharger PDF</span>
            </button>
            <button
              onClick={onClose}
              className="p-2 text-slate-500 hover:text-slate-800 rounded-xl hover:bg-slate-200 transition"
              title="Fermer (Échap)"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {loading ? (
          <div className="p-16 text-center">
            <Loader2 className="w-8 h-8 text-blue-600 animate-spin mx-auto mb-2" />
            <p className="text-xs text-slate-500 font-medium">Génération et chargement du document officiel...</p>
          </div>
        ) : (
          /* ====== PRINTABLE & DOWNLOADABLE CONTENT ====== */
          <div className="p-6 sm:p-12 bg-[#fefcf9] border-4 sm:border-8 border-blue-900/8 m-2 sm:m-4 rounded-2xl print:m-0 print:border-2 print:p-6 text-slate-800">

            {/* ── HEADER ── */}
            <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center pb-5 border-b-2 border-blue-900/20 gap-4">
              <div className="flex items-center gap-3">
                <div className="w-12 h-12 rounded-2xl bg-blue-900 text-white flex items-center justify-center shadow-md shrink-0">
                  <Droplets className="w-7 h-7 text-sky-400" />
                </div>
                <div>
                  <h1 className="text-2xl font-black tracking-tight text-blue-950 font-serif">
                    ECO<span className="text-blue-600">POWER</span> TUNISIE
                  </h1>
                  <p className="text-[10px] uppercase font-extrabold tracking-widest text-slate-400">
                    ECOGAM SARL • ECEAU-LOGIS
                  </p>
                </div>
              </div>

              <div className="text-left sm:text-right border-l-2 sm:border-l-0 border-blue-600 pl-3 sm:pl-0">
                <span className="text-[10px] uppercase font-bold text-slate-400 tracking-wider block">N° Certificat & Facture</span>
                <span className="font-mono text-sm sm:text-base font-extrabold text-blue-900">
                  {certificate.certificateSerial}
                </span>
                <span className="text-[10px] text-slate-500 block">
                  Date : {certificate.issueDate ? new Date(certificate.issueDate).toLocaleDateString('fr-FR') : new Date().toLocaleDateString('fr-FR')}
                </span>
              </div>
            </div>

            {/* ── TITLE ── */}
            <div className="py-4 text-center space-y-1">
              <span className="text-[11px] uppercase font-extrabold tracking-widest text-blue-800 bg-blue-100/70 px-3.5 py-0.5 rounded-full">
                Document d'Agrément Technique & Facture d'Achat
              </span>
              <h2 className="text-xl sm:text-2xl font-black text-slate-900 font-serif pt-1">
                CERTIFICAT DE GARANTIE 3 ANS & FACTURE
              </h2>
              <p className="text-[11px] text-slate-500 max-w-xl mx-auto">
                Atteste de la conformité des équipements hydro-économes aux normes internationales ISO 9001 et sanitaires ACS.
              </p>
            </div>

            {/* ── BENEFICIARY & ORDER INFO ── */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 p-3.5 bg-slate-50 rounded-2xl border border-slate-200 text-xs mb-5">
              <div>
                <span className="text-slate-400 text-[10px] uppercase font-bold">Client / Bénéficiaire :</span>
                <div className="font-extrabold text-slate-900 text-sm mt-0.5">{certificate.customerName || 'Client Particulier'}</div>
                <div className="text-slate-600 text-[11px]">{certificate.customerAddress || 'Tunisie'}</div>
              </div>
              <div>
                <span className="text-slate-400 text-[10px] uppercase font-bold">Coordonnées & Réf :</span>
                <div className="font-mono text-slate-800 text-xs mt-0.5">{certificate.customerPhone || '+216 -- --- ---'}</div>
                <div className="text-slate-600 text-[11px]">Réf. Commande : <strong>{certificate.orderId}</strong></div>
              </div>
            </div>

            {/* ── 1. INVOICE / FACTURE TABLE WITH REAL PRICES ── */}
            <div className="mb-5">
              <h3 className="text-xs uppercase font-extrabold tracking-wider text-slate-700 mb-2 flex items-center gap-1.5">
                <FileText className="w-3.5 h-3.5 text-blue-600" />
                Détail de la Facture :
              </h3>
              <div className="border border-slate-200 rounded-xl overflow-hidden bg-white text-xs">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="bg-slate-100 text-slate-700 font-bold border-b border-slate-200">
                      <th className="p-2 sm:p-2.5">Désignation du Produit</th>
                      <th className="p-2 sm:p-2.5 text-center">Qté</th>
                      <th className="p-2 sm:p-2.5 text-right">Prix Unit.</th>
                      <th className="p-2 sm:p-2.5 text-right">Total</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {certificate.items?.map((item, idx) => {
                      const itemPrice = (item.price && parseFloat(item.price) > 0) 
                        ? parseFloat(item.price) 
                        : (item.name?.toLowerCase().includes('maison') ? 129.0 : 78.0);
                      const qty = item.quantity || 1;
                      const lineTotal = itemPrice * qty;

                      return (
                        <tr key={idx} className="hover:bg-slate-50/50">
                          <td className="p-2 sm:p-2.5 text-slate-900 font-semibold">{item.name}</td>
                          <td className="p-2 sm:p-2.5 text-center font-mono">{qty}</td>
                          <td className="p-2 sm:p-2.5 text-right font-mono">{itemPrice.toFixed(2)} DT</td>
                          <td className="p-2 sm:p-2.5 text-right font-bold font-mono text-blue-900">{lineTotal.toFixed(2)} DT</td>
                        </tr>
                      );
                    })}
                    {discount > 0 && (
                      <tr className="bg-slate-50 border-t border-slate-200">
                        <td className="p-2 sm:p-2.5 text-blue-700 font-medium" colSpan="3">
                          Remise retrait au local (-10%)
                        </td>
                        <td className="p-2 sm:p-2.5 text-right font-mono font-bold text-blue-700">
                          -{discount.toFixed(2)} DT
                        </td>
                      </tr>
                    )}
                    <tr className="bg-slate-50 border-t border-slate-200">
                      <td className="p-2 sm:p-2.5 text-slate-600 font-medium" colSpan="3">
                        {isPickup ? 'Retrait au local (sans frais de livraison)' : 'Frais de livraison rapide à domicile (Tunisie)'}
                      </td>
                      <td className="p-2 sm:p-2.5 text-right font-mono font-bold text-slate-700">
                        {deliveryFee.toFixed(2)} DT
                      </td>
                    </tr>
                    <tr className="bg-blue-50 border-t-2 border-blue-200 font-black text-blue-950">
                      <td className="p-2.5 sm:p-3 text-xs uppercase" colSpan="3">
                        MONTANT TOTAL NET À PAYER (TTC)
                      </td>
                      <td className="p-2.5 sm:p-3 text-right font-mono text-sm sm:text-base text-blue-900">
                        {total.toFixed(2)} DT
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>

            {/* ── 2. ARTICLES & NUMÉROS DE SÉRIE GRAVÉS ── */}
            <div className="mb-5">
              <h3 className="text-xs uppercase font-extrabold tracking-wider text-slate-700 mb-2 flex items-center gap-1.5">
                <Package className="w-3.5 h-3.5 text-blue-600" />
                Matériels Couverts par la Garantie Constructeur :
              </h3>
              <div className="border border-slate-200 rounded-xl overflow-hidden bg-white text-xs">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="bg-slate-100 text-slate-700 font-bold border-b border-slate-200">
                      <th className="p-2 sm:p-2.5">Article</th>
                      <th className="p-2 sm:p-2.5 text-center">Qté</th>
                      <th className="p-2 sm:p-2.5">Numéro(s) de Série Gravé(s)</th>
                      <th className="p-2 sm:p-2.5 text-right">Durée Garantie</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {certificate.items?.map((item, idx) => (
                      <tr key={idx} className="hover:bg-slate-50/50">
                        <td className="p-2 sm:p-2.5 font-bold text-slate-900">{item.name}</td>
                        <td className="p-2 sm:p-2.5 text-center font-mono">{item.quantity || 1}</td>
                        <td className="p-2 sm:p-2.5 font-mono text-blue-900 font-bold text-[11px]">
                          {item.serials && item.serials.length > 0 ? item.serials.join(', ') : `SN-ECO-2026-${certificate.orderId}-${idx + 1}`}
                        </td>
                        <td className="p-2 sm:p-2.5 text-right font-black text-blue-700">
                          {item.name?.toLowerCase().includes('sac') ? 'À VIE' : '3 ANS'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* ── NORMS & SPECIFICATIONS ── */}
            <div className="p-3.5 bg-blue-50/60 rounded-2xl border border-blue-200/60 text-xs space-y-1.5 mb-5">
              <div className="flex items-center gap-2 font-bold text-slate-800">
                <ShieldCheck className="w-4 h-4 text-blue-600" />
                <span>Normes Sanitaires & Spécifications Techniques :</span>
              </div>
              <ul className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-slate-600 text-[11px]">
                <li className="flex items-start gap-1.5">
                  <CheckCircle className="w-3.5 h-3.5 text-blue-600 shrink-0 mt-0.5" />
                  <span>Résistance testée sous haute pression jusqu'à <strong>25 Bars</strong></span>
                </li>
                <li className="flex items-start gap-1.5">
                  <CheckCircle className="w-3.5 h-3.5 text-blue-600 shrink-0 mt-0.5" />
                  <span>Matériau breveté <strong>Delrin / Hostaform</strong> antitartre & anticalcaire</span>
                </li>
                <li className="flex items-start gap-1.5">
                  <CheckCircle className="w-3.5 h-3.5 text-blue-600 shrink-0 mt-0.5" />
                  <span>Certifié <strong>ACS</strong> (Attestation de Conformité Sanitaire)</span>
                </li>
                <li className="flex items-start gap-1.5">
                  <CheckCircle className="w-3.5 h-3.5 text-blue-600 shrink-0 mt-0.5" />
                  <span>Conforme aux exigences d'audit <strong>ISO 9001</strong></span>
                </li>
              </ul>
            </div>

            {/* ── FOOTER & OFFICIAL VISA ── */}
            <div className="pt-4 border-t border-slate-200 flex flex-col sm:flex-row justify-between items-end gap-4">
              <div className="text-[10px] text-slate-500 space-y-0.5">
                <p><strong>ECOGAM SARL / ECOPOWER TUNISIE</strong></p>
                <p>Direction Technique & Service Qualité Pascal FABRE</p>
                <p>Contact : eceau-lo@orange.fr / +216 97 644 988</p>
              </div>

              <div className="text-center p-2.5 border-2 border-dashed border-blue-600/40 rounded-2xl bg-white w-44 shadow-xs">
                <div className="w-7 h-7 mx-auto rounded-full bg-blue-100 flex items-center justify-center text-blue-800 mb-1">
                  <Award className="w-4 h-4 text-blue-700" />
                </div>
                <span className="text-[9px] font-black uppercase text-blue-900 block leading-tight">
                  CERTIFIÉ CONFORME
                </span>
                <span className="text-[8px] text-slate-500 block">Visa Qualité Technique</span>
                <span className="text-[8px] font-mono text-blue-700 font-bold block mt-0.5">GARANTIE VALIDÉE</span>
              </div>
            </div>

          </div>
        )}
      </div>
    </div>
  );
};
