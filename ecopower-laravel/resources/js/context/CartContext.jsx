import React, { createContext, useContext, useState, useEffect } from 'react';
import { pickupDiscountFor, DEFAULT_PICKUP_INFO } from '../lib/pickup';

const CartContext = createContext();

export const CartProvider = ({ children }) => {
  const [cart, setCart] = useState(() => {
    try {
      const saved = localStorage.getItem('ecopower_cart');
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });

  const [isCartOpen, setIsCartOpen] = useState(false);
  const [isCheckoutOpen, setIsCheckoutOpen] = useState(false);
  // 'delivery' (livraison à domicile) ou 'pickup' (retrait au local, packs éligibles uniquement)
  const [deliveryMethod, setDeliveryMethod] = useState('delivery');
  // 'cod' (espèces) ou 'card' (carte bancaire via Konnect, si activé côté serveur)
  const [paymentMethod, setPaymentMethod] = useState('cod');
  const [shopInfo, setShopInfo] = useState({ card: false, pickup: DEFAULT_PICKUP_INFO });

  useEffect(() => {
    fetch('/api/payments/methods')
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => data && setShopInfo({ card: !!data.card, pickup: { ...DEFAULT_PICKUP_INFO, ...data.pickup } }))
      .catch(() => {});
  }, []);
  const [language, setLanguage] = useState(() => {
    return localStorage.getItem('ecopower_lang') || 'fr';
  });

  useEffect(() => {
    localStorage.setItem('ecopower_cart', JSON.stringify(cart));
  }, [cart]);

  useEffect(() => {
    localStorage.setItem('ecopower_lang', language);
    document.documentElement.dir = language === 'ar' ? 'rtl' : 'ltr';
    document.documentElement.lang = language;
  }, [language]);

  const addToCart = (product, quantity = 1) => {
    setCart((prev) => {
      const existing = prev.find((item) => item.product.id === product.id);
      if (existing) {
        return prev.map((item) =>
          item.product.id === product.id
            ? { ...item, quantity: item.quantity + quantity }
            : item
        );
      }
      return [...prev, { product, quantity }];
    });
    setIsCartOpen(true);
  };

  const removeFromCart = (productId) => {
    setCart((prev) => prev.filter((item) => item.product.id !== productId));
  };

  const updateQuantity = (productId, quantity) => {
    if (quantity <= 0) {
      removeFromCart(productId);
      return;
    }
    setCart((prev) =>
      prev.map((item) =>
        item.product.id === productId ? { ...item, quantity } : item
      )
    );
  };

  const clearCart = () => {
    setCart([]);
  };

  const totalItems = cart.reduce((sum, item) => sum + item.quantity, 0);

  const subtotal = Math.round(
    cart.reduce((sum, item) => sum + item.product.price * item.quantity, 0) * 100
  ) / 100;

  const pickupIds = shopInfo.pickup.productIds || [];
  const isPickupProduct = (productId) => pickupIds.includes(productId);
  const canPickup = cart.some((item) => isPickupProduct(item.product.id));
  const isPickup = canPickup && deliveryMethod === 'pickup';
  const pickupDiscount = pickupDiscountFor(cart, pickupIds);
  const discount = isPickup ? pickupDiscount : 0;

  const deliveryFee = cart.length === 0 || isPickup ? 0 : subtotal >= 120 ? 0 : 8.0;

  const total = Math.round((subtotal - discount + deliveryFee) * 100) / 100;

  return (
    <CartContext.Provider
      value={{
        cart,
        addToCart,
        removeFromCart,
        updateQuantity,
        clearCart,
        totalItems,
        subtotal,
        deliveryFee,
        total,
        canPickup,
        isPickupProduct,
        isPickup,
        pickupDiscount,
        discount,
        deliveryMethod: isPickup ? 'pickup' : 'delivery',
        setDeliveryMethod,
        paymentMethod: shopInfo.card ? paymentMethod : 'cod',
        setPaymentMethod,
        cardEnabled: shopInfo.card,
        pickupInfo: shopInfo.pickup,
        isCartOpen,
        setIsCartOpen,
        isCheckoutOpen,
        setIsCheckoutOpen,
        language,
        setLanguage,
      }}
    >
      {children}
    </CartContext.Provider>
  );
};

export const useCart = () => useContext(CartContext);
