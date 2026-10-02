import React from 'react';
import { useCart } from '../context/CartContext';
import { X, Trash2, Plus, Minus, ShoppingBag, ArrowRight, ShieldCheck, Truck } from 'lucide-react';

export const CartDrawer = () => {
  const {
    cart,
    isCartOpen,
    setIsCartOpen,
    removeFromCart,
    updateQuantity,
    subtotal,
    deliveryFee,
    total,
    setIsCheckoutOpen,
    language
  } = useCart();

  if (!isCartOpen) return null;

  const freeDeliveryThreshold = 120;
  const remainingForFreeDelivery = Math.max(0, freeDeliveryThreshold - subtotal);
  const freeDeliveryPercent = Math.min(100, Math.round((subtotal / freeDeliveryThreshold) * 100));

  return (
    <div className="fixed inset-0 z-50 overflow-hidden">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-slate-900/60 backdrop-blur-xs transition-opacity animate-in fade-in duration-200"
        onClick={() => setIsCartOpen(false)}
      />

      <div className="fixed inset-y-0 right-0 max-w-full flex pl-10">
        <div className="w-screen max-w-md bg-white shadow-2xl flex flex-col animate-in slide-in-from-right duration-300">
          
          {/* Header */}
          <div className="p-5 border-b border-slate-200 flex items-center justify-between bg-slate-50">
            <div className="flex items-center gap-2">
              <ShoppingBag className="w-5 h-5 text-blue-700" />
              <h2 className="font-extrabold text-lg text-slate-900">
                {language === 'ar' ? 'سلة المشتريات' : 'Mon Panier'}
              </h2>
              <span className="text-xs font-bold px-2 py-0.5 rounded-full bg-blue-100 text-blue-800">
                {cart.length} {cart.length > 1 ? 'articles' : 'article'}
              </span>
            </div>
            <button
              onClick={() => setIsCartOpen(false)}
              className="p-2 text-slate-400 hover:text-slate-700 rounded-xl hover:bg-slate-200/60 transition"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Free delivery progress */}
          <div className="px-5 py-3 bg-blue-50/70 border-b border-blue-100 text-xs">
            {remainingForFreeDelivery > 0 ? (
              <div>
                <p className="text-blue-900 font-semibold mb-1.5 flex items-center gap-1.5">
                  <Truck className="w-4 h-4 text-blue-600" />
                  Plus que <span className="font-black text-blue-700">{remainingForFreeDelivery.toFixed(2)} DT</span> pour la livraison offerte !
                </p>
                <div className="w-full bg-blue-200 h-1.5 rounded-full overflow-hidden">
                  <div
                    className="bg-blue-600 h-full rounded-full transition-all duration-500"
                    style={{ width: `${freeDeliveryPercent}%` }}
                  />
                </div>
              </div>
            ) : (
              <p className="text-blue-800 font-bold flex items-center gap-1.5">
                <ShieldCheck className="w-4 h-4 text-blue-600" />
                Félicitations ! Vous bénéficiez de la livraison gratuite sur votre commande 🎉
              </p>
            )}
          </div>

          {/* Cart items list */}
          <div className="flex-1 overflow-y-auto p-5 divide-y divide-slate-100">
            {cart.length === 0 ? (
              <div className="h-full flex flex-col items-center justify-center text-center p-6">
                <div className="w-16 h-16 rounded-full bg-slate-100 flex items-center justify-center text-slate-400 mb-4">
                  <ShoppingBag className="w-8 h-8" />
                </div>
                <h3 className="font-bold text-slate-800 text-lg">Votre panier est vide</h3>
                <p className="text-slate-500 text-sm mt-1 mb-6">
                  Découvrez nos packs économiques pour réduire vos factures dès aujourd'hui.
                </p>
                <button
                  onClick={() => setIsCartOpen(false)}
                  className="bg-blue-600 hover:bg-blue-700 text-white font-bold py-2.5 px-6 rounded-xl text-sm transition"
                >
                  Découvrir les produits
                </button>
              </div>
            ) : (
              cart.map((item) => (
                <div key={item.product.id} className="py-4 flex gap-4 items-center">
                  <img
                    src={item.product.image}
                    alt={item.product.name}
                    className="w-16 h-16 rounded-xl object-cover border border-slate-200 shrink-0 bg-slate-50"
                  />
                  <div className="flex-1 min-w-0">
                    <h4 className="font-bold text-sm text-slate-900 truncate">
                      {item.product.name}
                    </h4>
                    <p className="text-xs text-blue-700 font-bold mt-0.5">
                      {item.product.price.toFixed(2)} DT
                    </p>
                    <div className="flex items-center gap-2 mt-2">
                      <div className="flex items-center border border-slate-200 rounded-lg overflow-hidden bg-slate-50">
                        <button
                          onClick={() => updateQuantity(item.product.id, item.quantity - 1)}
                          className="px-2 py-1 text-slate-600 hover:bg-slate-200 transition"
                        >
                          <Minus className="w-3.5 h-3.5" />
                        </button>
                        <span className="px-2.5 py-1 text-xs font-bold text-slate-800 min-w-[24px] text-center">
                          {item.quantity}
                        </span>
                        <button
                          onClick={() => updateQuantity(item.product.id, item.quantity + 1)}
                          className="px-2 py-1 text-slate-600 hover:bg-slate-200 transition"
                        >
                          <Plus className="w-3.5 h-3.5" />
                        </button>
                      </div>
                      <span className="text-xs font-black text-slate-700 ml-auto">
                        {(item.product.price * item.quantity).toFixed(2)} DT
                      </span>
                    </div>
                  </div>
                  <button
                    onClick={() => removeFromCart(item.product.id)}
                    className="text-slate-400 hover:text-red-500 p-1.5 transition"
                    title="Supprimer"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              ))
            )}
          </div>

          {/* Footer with totals */}
          {cart.length > 0 && (
            <div className="p-5 border-t border-slate-200 bg-slate-50 space-y-3">
              <div className="space-y-1.5 text-sm">
                <div className="flex justify-between text-slate-600">
                  <span>Sous-total articles :</span>
                  <span className="font-semibold text-slate-800">{subtotal.toFixed(2)} DT</span>
                </div>
                <div className="flex justify-between text-slate-600">
                  <span>Frais de livraison (Tunisie) :</span>
                  <span className="font-semibold">
                    {deliveryFee === 0 ? (
                      <span className="text-blue-600 font-bold">Gratuit</span>
                    ) : (
                      `${deliveryFee.toFixed(2)} DT`
                    )}
                  </span>
                </div>
                <div className="border-t border-slate-200 pt-2 flex justify-between text-base font-extrabold text-slate-900">
                  <span>Total à payer :</span>
                  <span className="text-blue-800 text-lg">{total.toFixed(2)} DT</span>
                </div>
              </div>

              <button
                onClick={() => {
                  setIsCartOpen(false);
                  setIsCheckoutOpen(true);
                }}
                className="w-full bg-blue-600 hover:bg-blue-700 active:bg-blue-800 text-white font-extrabold py-3.5 px-4 rounded-xl text-sm flex items-center justify-center gap-2 shadow-lg shadow-blue-500/25 transition-all hover:scale-[1.01]"
              >
                <span>Valider la Commande (Paiement à la livraison)</span>
                <ArrowRight className="w-4 h-4" />
              </button>

              <div className="text-center">
                <p className="text-[11px] text-slate-600 flex items-center justify-center gap-1">
                  <ShieldCheck className="w-3.5 h-3.5 text-blue-600" />
                  Garantie 3 ans &amp; Certificat officiel fourni avec votre colis
                </p>
              </div>
            </div>
          )}

        </div>
      </div>
    </div>
  );
};
