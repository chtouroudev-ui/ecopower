import React, { useState, useEffect } from 'react';
import { useCart } from '../context/CartContext';
import { SEO } from '../components/SEO';
import { 
  ShoppingBag, 
  Search, 
  Filter, 
  ShieldCheck, 
  CheckCircle2, 
  Star, 
  Eye, 
  X, 
  Truck,
  Sparkles
} from 'lucide-react';

export const ShopPage = () => {
  const { addToCart, language } = useCart();
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedCategory, setSelectedCategory] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [activeModalProduct, setActiveModalProduct] = useState(null);

  useEffect(() => {
    fetch('/api/products')
      .then((res) => res.json())
      .then((data) => {
        setProducts(data);
        setLoading(false);
      })
      .catch((err) => {
        console.error('Error fetching products:', err);
        setLoading(false);
      });
  }, []);

  const categories = [
    { id: 'all', label: 'Tous les Articles' },
    { id: 'packs', label: '🎁 Packs Complets' },
    { id: 'robinets', label: '🚰 Hydro-Économes Robinets' },
    { id: 'douches', label: '🚿 Douches & Pommeaux' },
    { id: 'wc', label: '🚽 Économiseurs WC' },
    { id: 'accessoires', label: '🔧 Bagues & Joints Inox' },
    { id: 'energie', label: '💡 Énergie & Ampoules LED' },
  ];

  const filteredProducts = products.filter((p) => {
    const matchesCat = selectedCategory === 'all' || p.category === selectedCategory;
    const matchesSearch =
      p.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (p.description && p.description.toLowerCase().includes(searchQuery.toLowerCase()));
    return matchesCat && matchesSearch;
  });

  return (
    <div className="py-10 space-y-10 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
   <SEO
  title="Boutique hydro-économes pour réduire sa facture SONEDE | EcoPower"
  description="Pommes de douche, éco-robinets et packs hydro-économes pour réduire votre facture SONEDE. Livraison 24-48h partout en Tunisie, paiement à la livraison."
  path="/shop"
/>
      {/* Top Banner */}
      <div className="bg-gradient-to-r from-brand-900 via-brand-800 to-skywater-700 text-white rounded-3xl p-8 sm:p-12 shadow-xl relative overflow-hidden flex flex-col sm:flex-row justify-between items-start sm:items-center gap-6">
        <div>
          <span className="px-3 py-1 bg-white/10 rounded-full text-sky-300 text-xs font-bold uppercase tracking-wider border border-white/20">
            Boutique Officielle EcoPower Tunisie
          </span>
          <h1 className="text-3xl sm:text-4xl font-black font-serif tracking-tight text-white mt-2">
            Dispositifs Hydro-Économes Certifiés
          </h1>
          <p className="text-slate-200 text-xs sm:text-sm mt-1 max-w-xl">
            Packs et articles au détail certifiés Hostaform/Delrin. Prix en Dinars Tunisiens (DT). Livraison rapide 24-48h à domicile avec paiement en espèces.
          </p>
        </div>

        <div className="flex items-center gap-3 bg-white/10 backdrop-blur-md px-5 py-3 rounded-2xl border border-white/20 text-xs font-semibold">
          <Truck className="w-5 h-5 text-sky-300" />
          <div>
            <div className="text-white font-bold">Livraison Partout en Tunisie</div>
            <div className="text-slate-300 text-[11px]">Gratuite dès 120 DT d'achat</div>
          </div>
        </div>
      </div>

      {/* Filters & Search Bar */}
      <div className="bg-white p-4 sm:p-6 rounded-3xl border border-slate-200 shadow-xs space-y-4">
        <div className="flex flex-col sm:flex-row gap-4 justify-between items-center">
          
          {/* Search Input */}
          <div className="relative w-full sm:w-80">
            <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Rechercher un produit, débit, pack..."
              className="w-full pl-10 pr-4 py-2.5 rounded-xl border border-slate-200 text-sm focus:border-brand-500 focus:ring-2 focus:ring-brand-200 outline-none transition"
            />
          </div>

          <div className="text-xs text-slate-600 font-semibold self-end sm:self-center">
            {filteredProducts.length} {filteredProducts.length > 1 ? 'articles trouvés' : 'article trouvé'}
          </div>
        </div>

        {/* Category Pills */}
        <div className="flex items-center gap-2 overflow-x-auto pb-2 scrollbar-none">
          {categories.map((cat) => (
            <button
              key={cat.id}
              onClick={() => setSelectedCategory(cat.id)}
              className={`px-4 py-2 rounded-xl text-xs font-bold whitespace-nowrap transition-all ${
                selectedCategory === cat.id
                  ? 'bg-brand-700 text-white shadow-xs scale-105'
                  : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
              }`}
            >
              {cat.label}
            </button>
          ))}
        </div>
      </div>

      {/* Products Grid */}
      {loading ? (
        <div className="py-20 text-center">
          <div className="w-10 h-10 border-4 border-brand-700 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
          <p className="text-xs font-bold text-slate-500">Chargement des produits...</p>
        </div>
      ) : filteredProducts.length === 0 ? (
        <div className="bg-white rounded-3xl p-12 text-center border border-slate-200">
          <p className="text-slate-500 font-bold">Aucun article ne correspond à votre recherche.</p>
          <button
            onClick={() => { setSelectedCategory('all'); setSearchQuery(''); }}
            className="mt-4 px-4 py-2 bg-brand-700 text-white rounded-xl text-xs font-bold"
          >
            Réinitialiser les filtres
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
          {filteredProducts.map((product) => (
            <div
              key={product.id}
              className="bg-white rounded-3xl border border-slate-200/90 shadow-2xs hover:shadow-xl transition-all duration-300 flex flex-col justify-between overflow-hidden group hover:-translate-y-1"
            >
              <div>
                {/* Image Box */}
            
<div className="h-52 bg-slate-50 relative p-4 flex items-center justify-center border-b border-slate-100 overflow-hidden">

  {/* Badge Pack Éco */}
  {product.category === 'packs' && (
    <span className="absolute top-2 left-2 bg-energy-500 text-white text-[9px] font-black uppercase px-2 py-1 rounded-full shadow-sm z-10">
      Pack Éco
    </span>
  )}

  {/* Badge Garantie */}
  {product.warranty && (
    <span className="absolute top-2 right-2 bg-white/95 text-brand-800 text-[9px] font-bold px-2 py-1 rounded-md border border-slate-200 shadow-sm z-10">
      Garantie {product.warranty}
    </span>
  )}

  <img
    src={product.image}
    alt={product.name}
    className="max-h-[85%] max-w-[85%] object-contain mt-5 group-hover:scale-105 transition-transform duration-300"
    loading="lazy"
  />

  {/* Bouton Détails */}
  <button
    onClick={() => setActiveModalProduct(product)}
    className="absolute inset-0 bg-slate-900/30 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center text-white gap-2 font-bold text-xs"
  >
    <div className="bg-white text-slate-900 px-3 py-1.5 rounded-xl shadow-md flex items-center gap-1.5 hover:scale-105 transition">
      <Eye className="w-3.5 h-3.5" />
      <span>Détails &amp; Fiche</span>
    </div>
  </button>

</div>


                {/* Content */}
                <div className="p-5">
                  <div className="flex items-center justify-between text-[11px] text-slate-600 mb-1 font-semibold">
                    <span className="uppercase tracking-wider">{product.category}</span>
                    {product.debit && (
                      <span className="text-brand-700 font-bold bg-brand-50 px-2 py-0.5 rounded-md">
                        {product.debit}
                      </span>
                    )}
                  </div>

                  <h3 className="font-extrabold text-sm sm:text-base text-slate-900 line-clamp-2 leading-snug group-hover:text-brand-700 transition">
                    {product.name}
                  </h3>

                  <p className="text-xs text-slate-600 mt-2 line-clamp-2 leading-relaxed">
                    {product.description}
                  </p>
                </div>
              </div>

              {/* Pricing & Add to Cart */}
              <div className="p-5 pt-0">
                <div className="flex items-baseline justify-between mb-3 border-t border-slate-100 pt-3">
                  <div>
                    {product.oldPrice && (
                      <span className="text-xs text-slate-400 line-through mr-1.5">
                        {product.oldPrice.toFixed(3)} DT
                      </span>
                    )}
                    <span className="text-xl font-black text-brand-900">
                      {product.price.toFixed(3)} <span className="text-xs font-bold text-slate-500">DT</span>
                    </span>
                  </div>
                  <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                    product.stock > 10 ? 'bg-blue-50 text-blue-700' : 'bg-amber-50 text-amber-700'
                  }`}>
                    {product.stock > 0 ? `En Stock (${product.stock})` : 'Sur Commande'}
                  </span>
                </div>

                <button
                  onClick={() => addToCart(product)}
                  className="w-full bg-gradient-to-r from-energy-500 to-energy-600 hover:from-energy-600 hover:to-energy-500 text-white font-extrabold py-2.5 px-4 rounded-xl text-xs flex items-center justify-center gap-2 shadow-md shadow-energy-500/20 transition-all hover:scale-[1.02] active:scale-98"
                >
                  <ShoppingBag className="w-4 h-4" />
                  <span>Ajouter au Panier</span>
                </button>
              </div>

            </div>
          ))}
        </div>
      )}

      {/* Product Detail Modal */}
      {activeModalProduct && (
        <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/70 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-3xl max-w-2xl w-full shadow-2xl border border-slate-200 overflow-hidden animate-in zoom-in-95 duration-200">
            
            <div className="p-5 border-b border-slate-200 flex items-center justify-between bg-slate-50">
              <span className="text-xs font-bold uppercase text-brand-700 tracking-wider">
                Fiche Technique Produit
              </span>
              <button
                onClick={() => setActiveModalProduct(null)}
                className="p-1.5 text-slate-400 hover:text-slate-700 rounded-xl hover:bg-slate-200 transition"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-6 sm:p-8 space-y-6">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-6 items-center">
                <div className="h-56 bg-slate-50 rounded-2xl border border-slate-100 p-4 flex items-center justify-center">
                  <img
                    src={activeModalProduct.image}
                    alt={activeModalProduct.name}
                    className="max-h-full max-w-full object-contain"
                  />
                </div>
                <div className="space-y-3">
                  <h3 className="text-xl font-extrabold text-slate-900 font-serif">
                    {activeModalProduct.name}
                  </h3>
                  <div className="text-2xl font-black text-brand-800">
                    {activeModalProduct.price.toFixed(3)} DT
                  </div>
                  <div className="flex flex-wrap gap-2 text-xs">
                    <span className="px-2.5 py-1 bg-brand-50 text-brand-800 font-bold rounded-lg">
                      Garantie : {activeModalProduct.warranty || '3 Ans'}
                    </span>
                    {activeModalProduct.debit && (
                      <span className="px-2.5 py-1 bg-skywater-50 text-skywater-800 font-bold rounded-lg">
                        Débit : {activeModalProduct.debit}
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-slate-600 leading-relaxed">
                    {activeModalProduct.description}
                  </p>
                </div>
              </div>

              {activeModalProduct.features && (
                <div className="space-y-2 border-t border-slate-100 pt-4">
                  <h4 className="text-xs font-bold text-slate-800 uppercase tracking-wider">
                    Points forts &amp; caractéristiques :
                  </h4>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs text-slate-600">
                    {activeModalProduct.features.map((feat, idx) => (
                      <div key={idx} className="flex items-center gap-2">
                        <CheckCircle2 className="w-4 h-4 text-blue-600 shrink-0" />
                        <span>{feat}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <div className="pt-4 border-t border-slate-100 flex gap-3">
                <button
                  onClick={() => {
                    addToCart(activeModalProduct);
                    setActiveModalProduct(null);
                  }}
                  className="flex-1 bg-gradient-to-r from-energy-500 to-energy-600 text-white font-extrabold py-3.5 px-4 rounded-xl text-sm flex items-center justify-center gap-2 shadow-lg shadow-energy-500/25 transition hover:scale-[1.01]"
                >
                  <ShoppingBag className="w-4 h-4" />
                  <span>Ajouter au Panier ({activeModalProduct.price.toFixed(3)} DT)</span>
                </button>
              </div>
            </div>

          </div>
        </div>
      )}

    </div>
  );
};
