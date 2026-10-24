import React, { useState } from 'react';
import { useCart } from '../context/CartContext';
import { X, CheckCircle, Truck, Banknote, ShieldCheck, FileCheck, ArrowRight, Loader2, PackageSearch } from 'lucide-react';

const GOVERNORATES = [
  'Tunis', 'Ariana', 'Ben Arous', 'Manouba', 'Nabeul', 'Zaghouan', 'Bizerte',
  'Béja', 'Jendouba', 'Le Kef', 'Siliana', 'Sousse', 'Monastir', 'Mahdia',
  'Sfax', 'Kairouan', 'Kasserine', 'Sidi Bouzid', 'Gabès', 'Médenine',
  'Tataouine', 'Gafsa', 'Tozeur', 'Kébili'
];

const EMPTY_FORM = {
  fullName: '',
  phone: '',
  governorate: 'Tunis',
  city: '',
  address: '',
  email: '',
  notes: '',
};

const normalizePhone = (value) => value.replace(/[^0-9]/g, '').replace(/^216/, '');

function validate(form) {
  const errors = {};
  if (form.fullName.trim().length < 3) errors.fullName = 'Indiquez votre nom et prénom.';
  if (!/^[2-9][0-9]{7}$/.test(normalizePhone(form.phone))) errors.phone = 'Numéro tunisien à 8 chiffres (ex : 98 123 456).';
  if (form.address.trim().length < 6) errors.address = 'Indiquez une adresse de livraison complète.';
  if (form.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email)) errors.email = 'Adresse email invalide.';
  return errors;
}

const inputClass = (hasError) =>
  `w-full px-3.5 py-2.5 rounded-xl border text-sm outline-none transition focus:ring-2 ${
    hasError ? 'border-red-300 focus:ring-red-200' : 'border-slate-200 focus:border-blue-600 focus:ring-blue-100'
  }`;

const Field = ({ label, required, error, children }) => (
  <div>
    <label className="block text-xs font-bold text-slate-700 mb-1">
      {label} {required && <span className="text-red-500">*</span>}
    </label>
    {children}
    {error && <p className="text-[11px] text-red-600 mt-1">{error}</p>}
  </div>
);

export const CheckoutModal = ({ onOrderPlaced, onTrackOrder }) => {
  const { cart, subtotal, deliveryFee, total, isCheckoutOpen, setIsCheckoutOpen, clearCart } = useCart();

  const [form, setForm] = useState(EMPTY_FORM);
  const [touched, setTouched] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [successOrder, setSuccessOrder] = useState(null);
  const [errorMessage, setErrorMessage] = useState('');

  if (!isCheckoutOpen) return null;

  const errors = touched ? validate(form) : {};
  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }));

  const close = () => {
    setIsCheckoutOpen(false);
    setSuccessOrder(null);
    setErrorMessage('');
    setTouched(false);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setTouched(true);
    if (Object.keys(validate(form)).length > 0) return;

    setIsSubmitting(true);
    setErrorMessage('');

    try {
      const res = await fetch('/api/orders', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          customer: {
            fullName: form.fullName.trim(),
            phone: normalizePhone(form.phone),
            email: form.email.trim(),
            governorate: form.governorate,
            city: form.city.trim() || form.governorate,
            address: form.address.trim(),
          },
          items: cart.map((item) => ({ productId: item.product.id, name: item.product.name, quantity: item.quantity })),
          notes: form.notes.trim(),
        }),
      });

      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(data.error || "Votre commande n'a pas pu être enregistrée.");
      }

      try {
        localStorage.setItem('ecopower_last_order', data.id);
      } catch {
        /* stockage indisponible */
      }
      setSuccessOrder(data);
      setForm(EMPTY_FORM);
      setTouched(false);
      clearCart();
      onOrderPlaced?.(data);
    } catch (err) {
      setErrorMessage(
        err instanceof TypeError
          ? 'Connexion impossible. Vérifiez votre connexion internet puis réessayez.'
          : err.message
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/70 backdrop-blur-sm flex items-start sm:items-center justify-center p-3 sm:p-4">
      <div
        role="dialog"
        aria-modal="true"
        className="bg-white rounded-3xl max-w-2xl w-full shadow-2xl border border-slate-200 overflow-hidden animate-in zoom-in-95 duration-200 my-4"
      >
        <div className="p-5 sm:p-6 bg-slate-50 border-b border-slate-200 flex items-center justify-between">
          <div>
            <h3 className="font-extrabold text-xl text-slate-900">
              {successOrder ? 'Commande confirmée' : 'Finaliser ma commande'}
            </h3>
            <p className="text-xs text-slate-500 mt-0.5">
              {successOrder ? 'Merci pour votre confiance' : 'Sans inscription · paiement en espèces à la livraison'}
            </p>
          </div>
          <button onClick={close} aria-label="Fermer" className="p-2 text-slate-400 hover:text-slate-700 rounded-xl hover:bg-slate-200/60 transition">
            <X className="w-5 h-5" />
          </button>
        </div>

        {successOrder ? (
          <div className="p-6 sm:p-8 text-center space-y-6">
            <div className="w-16 h-16 rounded-full bg-blue-100 text-blue-600 flex items-center justify-center mx-auto">
              <CheckCircle className="w-9 h-9" />
            </div>

            <div>
              <div className="text-xs font-bold uppercase tracking-wider text-slate-500">Numéro de commande</div>
              <div className="text-3xl font-black text-blue-900 font-mono mt-1">{successOrder.id}</div>
              <p className="text-slate-600 text-sm mt-3 max-w-md mx-auto">
                Notre équipe vous appelle au <strong>{successOrder.customer?.phone}</strong> pour confirmer la livraison (24 à 48 h).
                Gardez ce numéro pour suivre votre commande.
              </p>
            </div>

            <div className="p-4 bg-slate-50 rounded-2xl text-sm text-slate-600 text-left space-y-1.5">
              <div className="flex justify-between gap-4">
                <span>Destinataire</span>
                <strong className="text-slate-800 text-right">{successOrder.customer?.fullName}</strong>
              </div>
              <div className="flex justify-between gap-4">
                <span>Adresse</span>
                <strong className="text-slate-800 text-right">
                  {successOrder.customer?.address}, {successOrder.customer?.city || successOrder.customer?.governorate}
                </strong>
              </div>
              <div className="flex justify-between gap-4 pt-2 border-t border-slate-200 text-base font-bold text-slate-900">
                <span>À payer au livreur</span>
                <span className="text-blue-700">{Number(successOrder.total).toFixed(2)} DT</span>
              </div>
            </div>

            <div className="p-4 bg-blue-50 border border-blue-100 rounded-2xl text-left flex items-start gap-3">
              <FileCheck className="w-5 h-5 text-blue-600 shrink-0 mt-0.5" />
              <p className="text-xs text-blue-900">
                Certificat de garantie <strong className="font-mono">{successOrder.certificateSerial}</strong> : 3 ans sur les produits,
                à vie sur l'Eco-Sac. Il est joint à votre colis et consultable depuis le suivi de commande.
              </p>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {onTrackOrder && (
                <button
                  onClick={() => {
                    close();
                    onTrackOrder(successOrder.id);
                  }}
                  className="w-full border border-blue-200 text-blue-800 hover:bg-blue-50 font-bold py-3 px-6 rounded-xl transition flex items-center justify-center gap-2"
                >
                  <PackageSearch className="w-4 h-4" /> Suivre ma commande
                </button>
              )}
              <button onClick={close} className="w-full bg-blue-600 hover:bg-blue-700 text-white font-bold py-3 px-6 rounded-xl transition">
                Continuer mes achats
              </button>
            </div>
          </div>
        ) : (
          <form onSubmit={handleSubmit} noValidate className="p-5 sm:p-8 space-y-6">
            {errorMessage && (
              <div role="alert" className="p-3.5 bg-red-50 border border-red-200 text-red-700 rounded-xl text-sm font-semibold">
                {errorMessage}
              </div>
            )}

            <div className="space-y-4">
              <h4 className="font-extrabold text-sm text-slate-900 uppercase tracking-wider flex items-center gap-2">
                <Truck className="w-4 h-4 text-blue-600" /> Livraison
              </h4>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <Field label="Nom et prénom" required error={errors.fullName}>
                  <input type="text" autoComplete="name" value={form.fullName} onChange={set('fullName')} placeholder="Mohamed Trabelsi" className={inputClass(errors.fullName)} />
                </Field>
                <Field label="Téléphone" required error={errors.phone}>
                  <input type="tel" inputMode="numeric" autoComplete="tel" value={form.phone} onChange={set('phone')} placeholder="98 123 456" className={`${inputClass(errors.phone)} font-mono`} />
                </Field>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <Field label="Gouvernorat" required>
                  <select value={form.governorate} onChange={set('governorate')} className={`${inputClass(false)} bg-white`}>
                    {GOVERNORATES.map((gov) => (
                      <option key={gov} value={gov}>{gov}</option>
                    ))}
                  </select>
                </Field>
                <Field label="Ville / délégation">
                  <input type="text" autoComplete="address-level2" value={form.city} onChange={set('city')} placeholder="La Marsa, Ennasr, Hammamet…" className={inputClass(false)} />
                </Field>
              </div>

              <Field label="Adresse complète" required error={errors.address}>
                <input type="text" autoComplete="street-address" value={form.address} onChange={set('address')} placeholder="Rue, immeuble, étage, appartement" className={inputClass(errors.address)} />
              </Field>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <Field label="Email (facultatif)" error={errors.email}>
                  <input type="email" autoComplete="email" value={form.email} onChange={set('email')} placeholder="contact@exemple.tn" className={inputClass(errors.email)} />
                </Field>
                <Field label="Instructions (facultatif)">
                  <input type="text" value={form.notes} onChange={set('notes')} placeholder="Code porte, horaires…" className={inputClass(false)} />
                </Field>
              </div>
            </div>

            <div className="p-4 rounded-2xl border-2 border-blue-600 bg-blue-50/60 flex items-start gap-3">
              <Banknote className="w-5 h-5 text-blue-700 shrink-0 mt-0.5" />
              <div>
                <div className="font-extrabold text-sm text-slate-900">Paiement à la livraison</div>
                <div className="text-xs text-slate-600">Vous réglez en espèces au livreur, après vérification du colis. Aucun paiement en ligne.</div>
              </div>
            </div>

            <div className="p-4 bg-slate-50 rounded-2xl border border-slate-200 space-y-2 text-sm">
              {cart.map((item) => (
                <div key={item.product.id} className="flex justify-between gap-4 text-slate-600">
                  <span className="truncate">{item.quantity} × {item.product.name}</span>
                  <span className="tabular-nums shrink-0">{(item.product.price * item.quantity).toFixed(2)} DT</span>
                </div>
              ))}
              <div className="flex justify-between text-slate-600 pt-2 border-t border-slate-200">
                <span>Livraison</span>
                <span className="tabular-nums">{deliveryFee === 0 ? 'Offerte' : `${deliveryFee.toFixed(2)} DT`}</span>
              </div>
              <div className="flex justify-between font-black text-slate-900 text-base">
                <span>Total à payer à la livraison</span>
                <span className="text-blue-800 tabular-nums">{total.toFixed(2)} DT</span>
              </div>
              {subtotal < 120 && (
                <p className="text-[11px] text-slate-500">Livraison offerte dès 120 DT d'achat.</p>
              )}
            </div>

            <button
              type="submit"
              disabled={isSubmitting || cart.length === 0}
              className="w-full bg-blue-600 hover:bg-blue-700 text-white font-extrabold py-3.5 px-6 rounded-2xl text-base flex items-center justify-center gap-2 shadow-lg shadow-blue-500/25 transition disabled:opacity-60"
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin" /> Envoi de la commande…
                </>
              ) : (
                <>
                  Confirmer la commande <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>

            <div className="flex flex-wrap items-center justify-center gap-x-4 gap-y-1 text-[11px] text-slate-600">
              <span className="flex items-center gap-1">
                <ShieldCheck className="w-3.5 h-3.5 text-blue-600" /> Garantie 3 ans
              </span>
              <span>Satisfait ou remboursé 14 jours</span>
              <span>SAV en Tunisie</span>
            </div>
          </form>
        )}
      </div>
    </div>
  );
};
