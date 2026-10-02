import React, { useState } from 'react';
import { useCart } from '../context/CartContext';
import { 
  ShoppingBag, 
  Menu, 
  X, 
  Droplets, 
  Building2, 
  User, 
  Calculator, 
  ShieldCheck, 
  PhoneCall,
  LayoutDashboard
} from 'lucide-react';

export const Navbar = ({ currentTab, setCurrentTab }) => {
  const { totalItems, setIsCartOpen, language, setLanguage } = useCart();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const navLinks = [
    { id: 'home', label: language === 'ar' ? 'الرئيسية' : 'Accueil', icon: Droplets },
    { id: 'particuliers', label: language === 'ar' ? 'للأفراد' : 'Particuliers', icon: User },
    { id: 'professionnels', label: language === 'ar' ? 'للشركات والفنادق' : 'Professionnels B2B', icon: Building2 },
    { id: 'shop', label: language === 'ar' ? 'المتجر والباكات' : 'Boutique & Packs', icon: ShoppingBag },
    { id: 'calculator', label: language === 'ar' ? 'حاسبة التوفير' : 'Simulateur', icon: Calculator },
    { id: 'references', label: language === 'ar' ? 'مراجعنا' : 'Références', icon: ShieldCheck },
  ];

  return (
    <header className="sticky top-0 z-40 bg-white/95 backdrop-blur-md border-b border-slate-200/80 shadow-xs transition-all">
      {/* Top micro banner */}
      <div className="bg-brand-900 text-white text-xs py-1.5 px-4 font-medium tracking-wide">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="inline-block w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
            <span>
              {language === 'ar' 
                ? '⚡ وفر حتى 60% في الماء والغاز - توصيل سريع لكامل تراب الجمهورية خلال 24-48 ساعة'
                : '⚡ Économisez jusqu’à 60% d’eau et 25% de gaz • Livraison partout en Tunisie sous 24-48h'}
            </span>
          </div>
          <div className="hidden sm:flex items-center gap-4 text-emerald-200">
            <a href="tel:+21698000000" className="hover:text-white flex items-center gap-1 transition">
              <PhoneCall className="w-3.5 h-3.5" />
              <span>Service Client: +216 71 000 000</span>
            </a>
            <span>•</span>
            <button 
              onClick={() => setCurrentTab('admin')} 
              className="hover:text-white text-slate-300 flex items-center gap-1 transition font-semibold"
            >
              <LayoutDashboard className="w-3.5 h-3.5" />
              <span>Espace Admin</span>
            </button>
          </div>
        </div>
      </div>

      {/* Main navigation */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-20">
          
          {/* Logo */}
          <div 
            onClick={() => { setCurrentTab('home'); setMobileMenuOpen(false); }}
            className="flex items-center gap-3 cursor-pointer group select-none"
          >
            <div className="w-11 h-11 rounded-2xl bg-gradient-to-tr from-brand-700 via-brand-600 to-skywater-500 flex items-center justify-center text-white shadow-md shadow-brand-700/20 group-hover:scale-105 transition-transform">
              <Droplets className="w-6 h-6 animate-pulse" />
            </div>
            <div>
              <div className="flex items-center gap-1">
                <span className="font-extrabold text-2xl tracking-tight text-brand-900">ECO<span className="text-skywater-500">POWER</span></span>
                <span className="text-xs px-1.5 py-0.5 rounded-sm bg-brand-100 text-brand-800 font-bold uppercase tracking-wider">ECOGAM</span>
              </div>
              <p className="text-[11px] text-slate-600 font-medium tracking-tight">Hydro-Économie & Maîtrise de l'Énergie</p>
            </div>
          </div>

          {/* Desktop Links */}
          <nav className="hidden lg:flex items-center gap-1 xl:gap-2">
            {navLinks.map((link) => {
              const Icon = link.icon;
              const isActive = currentTab === link.id;
              return (
                <button
                  key={link.id}
                  onClick={() => setCurrentTab(link.id)}
                  className={`flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-sm font-semibold transition-all ${
                    isActive
                      ? 'bg-brand-50 text-brand-700 shadow-xs ring-1 ring-brand-200'
                      : 'text-slate-600 hover:text-brand-700 hover:bg-slate-50'
                  }`}
                >
                  <Icon className={`w-4 h-4 ${isActive ? 'text-brand-600' : 'text-slate-400'}`} />
                  <span>{link.label}</span>
                </button>
              );
            })}
          </nav>

          {/* Actions: Lang + Cart */}
          <div className="flex items-center gap-3">
            {/* Lang toggle */}
            <button
              onClick={() => setLanguage(language === 'fr' ? 'ar' : 'fr')}
              className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border border-slate-200 text-xs font-bold text-slate-700 hover:border-brand-500 hover:text-brand-700 transition"
              title="Changer de langue"
            >
              <span>{language === 'fr' ? '🇹🇳 العربية' : '🇫🇷 Français'}</span>
            </button>

            {/* Cart Button */}
            <button
              onClick={() => setIsCartOpen(true)}
              className="relative flex items-center gap-2 bg-gradient-to-r from-energy-500 to-energy-600 hover:from-energy-600 hover:to-energy-500 text-white px-4 py-2.5 rounded-xl font-bold text-sm shadow-md shadow-energy-500/25 transition-all hover:scale-105 active:scale-95"
            >
              <ShoppingBag className="w-5 h-5" />
              <span className="hidden sm:inline">{language === 'ar' ? 'السلة' : 'Panier'}</span>
              {totalItems > 0 && (
                <span className="w-5 h-5 flex items-center justify-center rounded-full bg-white text-energy-600 text-xs font-black shadow-xs">
                  {totalItems}
                </span>
              )}
            </button>

            {/* Mobile menu button */}
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="lg:hidden p-2 rounded-xl text-slate-600 hover:bg-slate-100 transition"
            >
              {mobileMenuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
            </button>
          </div>
        </div>
      </div>

      {/* Mobile Menu Dropdown */}
      {mobileMenuOpen && (
        <div className="lg:hidden border-t border-slate-200 bg-white px-4 pt-3 pb-6 shadow-xl animate-in slide-in-from-top-2 duration-200">
          <div className="flex flex-col gap-1.5">
            {navLinks.map((link) => {
              const Icon = link.icon;
              const isActive = currentTab === link.id;
              return (
                <button
                  key={link.id}
                  onClick={() => {
                    setCurrentTab(link.id);
                    setMobileMenuOpen(false);
                  }}
                  className={`flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-semibold text-left transition ${
                    isActive
                      ? 'bg-brand-50 text-brand-700 ring-1 ring-brand-200'
                      : 'text-slate-700 hover:bg-slate-50'
                  }`}
                >
                  <Icon className="w-5 h-5 text-brand-600" />
                  <span>{link.label}</span>
                </button>
              );
            })}
            
            <div className="pt-3 mt-2 border-t border-slate-100 flex items-center justify-between">
              <button
                onClick={() => {
                  setCurrentTab('admin');
                  setMobileMenuOpen(false);
                }}
                className="flex items-center gap-2 text-xs font-bold text-slate-600 hover:text-brand-700 p-2 rounded-lg"
              >
                <LayoutDashboard className="w-4 h-4" />
                <span>Accès Espace Administrateur</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </header>
  );
};
