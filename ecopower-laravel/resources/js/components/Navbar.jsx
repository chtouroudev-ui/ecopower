import React, { useState } from 'react';
import { useCart } from '../context/CartContext';
import { useAuth } from '../context/AuthContext';
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
  LayoutDashboard,
  Truck
} from 'lucide-react';

export const Navbar = ({ currentTab, setCurrentTab }) => {
  const { totalItems, setIsCartOpen, language, setLanguage } = useCart();
  const { isAdmin } = useAuth();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  // Streamlined primary links that never overflow
  const navLinks = [
    { id: 'home', label: language === 'ar' ? 'الرئيسية' : 'Accueil', icon: Droplets },
    { id: 'particuliers', label: language === 'ar' ? 'للأفراد' : 'Particuliers', icon: User },
    { id: 'professionnels', label: language === 'ar' ? 'للشركات' : 'Professionnels', icon: Building2 },
    { id: 'shop', label: language === 'ar' ? 'المتجر' : 'Boutique', icon: ShoppingBag },
    { id: 'calculator', label: language === 'ar' ? 'حاسبة التوفير' : 'Simulateur', icon: Calculator },
    { id: 'references', label: language === 'ar' ? 'مراجعنا' : 'Références', icon: ShieldCheck, mobileOnly: true },
    { id: 'tracking', label: language === 'ar' ? 'تتبع الطلبية' : 'Suivi commande', icon: Truck },
  ];

  return (
    <header className="sticky top-0 z-40 bg-white/95 backdrop-blur-md border-b border-slate-200/80 shadow-xs transition-all w-full overflow-hidden">
      {/* Top blue announcement bar */}
      <div className="bg-blue-950 text-white text-[11px] sm:text-xs py-1.5 px-3 sm:px-4 font-medium tracking-wide">
        <div className="max-w-7xl mx-auto flex items-center justify-between gap-2">
          <div className="flex items-center gap-2 truncate">
            <span className="inline-block w-2 h-2 rounded-full bg-blue-400 animate-pulse shrink-0"></span>
            <span className="truncate">
              {language === 'ar' 
                ? '⚡ وفّر حتى 60% في الماء و25% في الغاز • توصيل في 24-48 ساعة لكامل تونس'
                : '⚡ Économisez jusqu’à 60% d’eau et 25% de gaz • Livraison 24-48h partout en Tunisie'}
            </span>
          </div>
          <div className="hidden md:flex items-center gap-3 text-blue-200 shrink-0">
            <a href="tel:+21671000000" className="hover:text-white flex items-center gap-1 transition">
              <PhoneCall className="w-3.5 h-3.5 text-blue-400" />
              <span>{language === 'ar' ? 'خدمة الحرفاء:' : 'Service Client:'} <span dir="ltr">+216 71 000 000</span></span>
            </a>
            {isAdmin && (
              <>
                <span>•</span>
                <button 
                  onClick={() => setCurrentTab('admin')} 
                  className="hover:text-white text-blue-200 flex items-center gap-1 transition font-bold"
                >
                  <LayoutDashboard className="w-3.5 h-3.5 text-blue-400" />
                  <span>Panneau Admin</span>
                </button>
              </>
            )}
          </div>
        </div>
      </div>

      {/* Main navigation container */}
      <div className="max-w-7xl mx-auto px-3 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16 sm:h-20 gap-2 sm:gap-4">
          
          {/* Logo */}
          <div 
            onClick={() => { setCurrentTab('home'); setMobileMenuOpen(false); }}
            className="flex items-center gap-2.5 sm:gap-3 cursor-pointer select-none shrink-0"
          >
            <div className="w-10 h-10 sm:w-11 sm:h-11 rounded-2xl bg-gradient-to-tr from-blue-700 via-blue-600 to-sky-500 flex items-center justify-center text-white shadow-md shadow-blue-700/20 transition-transform">
              <Droplets className="w-5 h-5 sm:w-6 sm:h-6" />
            </div>
            <div>
              <div className="flex items-center gap-1">
                <span className="font-black text-xl sm:text-2xl tracking-tight text-blue-950">ECO<span className="text-blue-600">POWER</span></span>
              </div>
              <p className="hidden xl:block text-[11px] text-slate-500 font-medium tracking-tight">Hydro-Économie &amp; Maîtrise de l'Énergie</p>
            </div>
          </div>

          {/* Desktop Navigation Links */}
          <nav className="hidden xl:flex items-center gap-1">
            {navLinks.filter((l) => !l.mobileOnly).map((link) => {
              const Icon = link.icon;
              const isActive = currentTab === link.id;
              return (
                <button
                  key={link.id}
                  onClick={() => setCurrentTab(link.id)}
                  className={`flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs xl:text-sm font-semibold transition-all whitespace-nowrap ${
                    isActive
                      ? 'bg-blue-50 text-blue-700 shadow-xs ring-1 ring-blue-200'
                      : 'text-slate-600 hover:text-blue-700 hover:bg-slate-50'
                  }`}
                >
                  <Icon className={`w-4 h-4 ${isActive ? 'text-blue-600' : 'text-slate-400'}`} />
                  <span>{link.label}</span>
                </button>
              );
            })}
          </nav>

          {/* Medium screen Navigation Links (Compact text without icons) */}
          <nav className="hidden lg:flex xl:hidden items-center gap-0.5">
            {navLinks.filter((l) => !l.mobileOnly).map((link) => {
              const isActive = currentTab === link.id;
              return (
                <button
                  key={link.id}
                  onClick={() => setCurrentTab(link.id)}
                  className={`px-2.5 py-1.5 rounded-lg text-xs font-semibold transition-all whitespace-nowrap ${
                    isActive
                      ? 'bg-blue-50 text-blue-700 font-bold ring-1 ring-blue-200'
                      : 'text-slate-600 hover:text-blue-700 hover:bg-slate-50'
                  }`}
                >
                  <span>{link.label}</span>
                </button>
              );
            })}
          </nav>

          {/* Right Action Controls: User + Lang + Cart + Mobile Hamburger */}
          <div className="flex items-center gap-1.5 sm:gap-2 shrink-0">
            
            {/* Language Toggle */}
            <button
              onClick={() => setLanguage(language === 'fr' ? 'ar' : 'fr')}
              className="flex items-center gap-1 px-2 py-1.5 sm:px-2.5 sm:py-2 rounded-xl border border-slate-200 text-xs font-bold text-slate-700 hover:border-blue-500 hover:text-blue-700 transition"
              title="Changer de langue"
            >
              <span>{language === 'fr' ? '🇹🇳 AR' : '🇫🇷 FR'}</span>
            </button>

            {/* Cart Button */}
            <button
              onClick={() => setIsCartOpen(true)}
              className="relative flex items-center gap-1.5 sm:gap-2 bg-blue-600 hover:bg-blue-700 text-white px-3 py-1.5 sm:px-4 sm:py-2 rounded-xl font-bold text-xs sm:text-sm shadow-md shadow-blue-500/25 transition-all hover:scale-105 active:scale-95 shrink-0"
            >
              <ShoppingBag className="w-4 h-4 sm:w-5 sm:h-5" />
              <span className="hidden sm:inline">{language === 'ar' ? 'السلة' : 'Panier'}</span>
              {totalItems > 0 && (
                <span className="w-4 h-4 sm:w-5 sm:h-5 flex items-center justify-center rounded-full bg-white text-blue-700 text-[10px] sm:text-xs font-black shadow-xs">
                  {totalItems}
                </span>
              )}
            </button>

            {/* Mobile / Tablet Menu Button */}
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="lg:hidden p-2 rounded-xl text-slate-600 hover:bg-slate-100 transition shrink-0"
              aria-label="Menu"
            >
              {mobileMenuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
            </button>
          </div>
        </div>
      </div>

      {/* Mobile Drawer Navigation */}
      {mobileMenuOpen && (
        <div className="lg:hidden border-t border-slate-200 bg-white px-4 pt-3 pb-6 shadow-xl animate-in slide-in-from-top-2 duration-200">
          <div className="flex flex-col gap-1">
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
                      ? 'bg-blue-50 text-blue-700 ring-1 ring-blue-200 font-bold'
                      : 'text-slate-700 hover:bg-slate-50'
                  }`}
                >
                  <Icon className="w-5 h-5 text-blue-600" />
                  <span>{link.label}</span>
                </button>
              );
            })}

            <div className="pt-3 mt-2 border-t border-slate-100 flex flex-col gap-2">
              {isAdmin && (
                <button
                  onClick={() => {
                    setCurrentTab('admin');
                    setMobileMenuOpen(false);
                  }}
                  className="flex items-center gap-2 text-xs font-bold text-blue-700 bg-blue-50 p-2.5 rounded-xl"
                >
                  <LayoutDashboard className="w-4 h-4 text-blue-600" />
                  <span>Panneau d'Administration</span>
                </button>
              )}

            </div>
          </div>
        </div>
      )}
    </header>
  );
};
