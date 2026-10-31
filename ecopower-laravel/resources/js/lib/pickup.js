// Retrait au local : pas de frais de livraison et -10 % sur les produits cochés
// « Remise retrait au local » dans l'admin. Garder le même taux dans config/ecopower.php.
export const PICKUP_DISCOUNT_RATE = 0.1;

const round2 = (n) => Math.round(n * 100) / 100;

/** Remise retrait au local sur un panier [{ product, quantity }] pour les ids éligibles. */
export const pickupDiscountFor = (cart, productIds) =>
  round2(
    cart
      .filter((item) => productIds.includes(item.product.id))
      .reduce((sum, item) => sum + item.product.price * item.quantity, 0) * PICKUP_DISCOUNT_RATE
  );

// Valeurs par défaut, remplacées par celles du serveur (/api/payments/methods, config/ecopower.php).
export const DEFAULT_PICKUP_INFO = {
  address: 'Local EcoPower, rue Ibn Zohr, Tunis',
  hours: 'du lundi au samedi, de 7h à 12h',
  mapUrl: 'https://www.google.com/maps?q=36.822639,10.183694',
  productIds: ['pack-base', 'pack-totale'],
};
