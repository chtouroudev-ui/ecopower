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
  Truck,
  LogIn,
  LogOut,
  ChevronDown
} from 'lucide-react';

export const Navbar = ({ currentTab, setCurrentTab }) => {
  const { totalItems, setIsCartOpen, language, setLanguage } = useCart();
  const { user, isAuthenticated, isAdmin, openLogin, logout } = useAuth();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [userDropdownOpen, setUserDropdownOpen] = useState(false);

  const navLinks = [
    { id: 'home', label: language === 'ar' ? 'الرئيسية' : 'Accueil', icon: Droplets },
    { id: 'particuliers', label: language === 'ar' ? 'للأفراد' : 'Particuliers', icon: User },
    { id: 'professionnels', label: language === 'ar' ? 'للشركات والفنادق' : 'Professionnels B2B', icon: Building2 },
    { id: 'shop', label: language === 'ar' ? 'المتجر والباكات' : 'Boutique & Packs', icon: ShoppingBag },
    { id: 'calculator', label: language === 'ar' ? 'حاسبة التوفير' : 'Simulateur', icon: Calculator },
    { id: 'tracking', label: language === 'ar' ? 'تتبع الطلبية' : 'Suivi Commande', icon: Truck },
    { id: 'references', label: language === 'ar' ? 'مراجعنا' : 'Références', icon: ShieldCheck },
  ];

  return (
    <header className="sticky top-0 z-40 bg-white/95 backdrop-blur-md border-b border-slate-200/80 shadow-xs transition-all">
      {/* Top blue banner */}
      <div className="bg-blue-950 text-white text-xs py-1.5 px-4 font-medium tracking-wide">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="inline-block w-2 h-2 rounded-full bg-blue-400 animate-pulse"></span>
            <span>
              {language === 'ar' 
                ? '⚡ وفر حتى 60% في الماء والغاز - توصيل سريع لكامل تراب الجمهورية خلال 24-48 ساعة'
                : '⚡ Économisez jusqu’à 60% d’eau et 25% de gaz • Livraison partout en Tunisie sous 24-48h'}
            </span>
          </div>
          <div className="hidden sm:flex items-center gap-4 text-blue-200">
            <a href="tel:+21698000000" className="hover:text-white flex items-center gap-1 transition">
              <PhoneCall className="w-3.5 h-3.5" />
              <span>Service Client: +216 71 000 000</span>
            </a>
            <span>•</span>
            <button 
              onClick={() => setCurrentTab('admin')} 
              className="hover:text-white text-blue-200 flex items-center gap-1 transition font-semibold"
            >
              <LayoutDashboard className="w-3.5 h-3.5" />
              <span>{isAdmin ? 'Dashboard Admin (Connecté)' : 'Espace Admin'}</span>
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
            <div className="w-11 h-11 rounded-2xl bg-gradient-to-tr from-blue-700 via-blue-600 to-sky-500 flex items-center justify-center text-white shadow-md shadow-blue-700/20 group-hover:scale-105 transition-transform">
              <Droplets className="w-6 h-6 animate-pulse" />
            </div>
            <div>
              <div className="flex items-center gap-1">
                <span className="font-extrabold text-2xl tracking-tight text-blue-950">ECO<span className="text-blue-600">POWER</span></span>
                <span className="text-xs px-1.5 py-0.5 rounded-sm bg-blue-100 text-blue-800 font-bold uppercase tracking-wider">ECOGAM</span>
              </div>
              <p className="text-[11px] text-slate-500 font-medium tracking-tight">Hydro-Économie &amp; Maîtrise de l'Énergie</p>
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
                  className={`flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs xl:text-sm font-semibold transition-all ${
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

          {/* Actions: Auth + Lang + Cart */}
          <div className="flex items-center gap-2.5">
            {/* User Auth Button */}
            {isAuthenticated ? (
              <div className="relative">
                <button
                  onClick={() => setUserDropdownOpen(!userDropdownOpen)}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-blue-200 bg-blue-50 text-xs font-bold text-blue-900 hover:bg-blue-100 transition"
                >
                  <User className="w-3.5 h-3.5 text-blue-600" />
                  <span className="max-w-[100px] truncate">{user.name.split(' ')[0]}</span>
                  <ChevronDown className="w-3 h-3 text-blue-400" />
                </button>

                {userDropdownOpen && (
                  <div className="absolute right-0 mt-2 w-52 bg-white rounded-2xl shadow-xl border border-blue-100 py-2 z-50 animate-in fade-in zoom-in-95 duration-150">
                    <div className="px-4 py-2 border-b border-slate-100">
                      <p className="text-xs font-bold text-slate-800">{user.name}</p>
                      <p className="text-[11px] text-slate-400 truncate">{user.email}</p>
                    </div>
                    
                    <button
                      onClick={() => {
                        setCurrentTab('tracking');
                        setUserDropdownOpen(false);
                      }}
                      className="w-full px-4 py-2 text-left text-xs font-medium text-slate-700 hover:bg-blue-50 hover:text-blue-700 flex items-center gap-2"
                    >
                      <Truck className="w-3.5 h-3.5 text-blue-600" />
                      <span>Mes Commandes</span>
                    </button>

                    {isAdmin && (
                      <button
                        onClick={() => {
                          setCurrentTab('admin');
                          setUserDropdownOpen(false);
                        }}
                        className="w-full px-4 py-2 text-left text-xs font-medium text-blue-700 hover:bg-blue-50 flex items-center gap-2"
                      >
                        <LayoutDashboard className="w-3.5 h-3.5" />
                        <span>Panneau Admin</span>
                      </button>
                    )}

                    <div className="border-t border-slate-100 mt-1 pt-1">
                      <button
                        onClick={() => {
                          logout();
                          setUserDropdownOpen(false);
                        }}
                        className="w-full px-4 py-2 text-left text-xs font-medium text-red-600 hover:bg-red-50 flex items-center gap-2"
                      >
                        <LogOut className="w-3.5 h-3.5" />
                        <span>Déconnexion</span>
                      </button>
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <button
                onClick={openLogin}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-slate-200 text-xs font-bold text-slate-700 hover:border-blue-500 hover:text-blue-700 transition"
              >
                <LogIn className="w-3.5 h-3.5 text-blue-600" />
                <span className="hidden sm:inline">Connexion</span>
              </button>
            )}

            {/* Lang toggle */}
            <button
              onClick={() => setLanguage(language === 'fr' ? 'ar' : 'fr')}
              className="flex items-center gap-1 px-2 py-1.5 rounded-lg border border-slate-200 text-xs font-bold text-slate-700 hover:border-blue-500 hover:text-blue-700 transition"
              title="Changer de langue"
            >
              <span>{language === 'fr' ? '🇹🇳 AR' : '🇫🇷 FR'}</span>
            </button>

            {/* Cart Button - Blue Theme */}
            <button
              onClick={() => setIsCartOpen(true)}
              className="relative flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white px-3.5 py-2 rounded-xl font-bold text-xs sm:text-sm shadow-md shadow-blue-500/25 transition-all hover:scale-105 active:scale-95"
            >
              <ShoppingBag className="w-4 h-4 sm:w-5 sm:h-5" />
              <span className="hidden sm:inline">{language === 'ar' ? 'السلة' : 'Panier'}</span>
              {totalItems > 0 && (
                <span className="w-5 h-5 flex items-center justify-center rounded-full bg-white text-blue-700 text-xs font-black shadow-xs">
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
                      ? 'bg-blue-50 text-blue-700 ring-1 ring-blue-200'
                      : 'text-slate-700 hover:bg-slate-50'
                  }`}
                >
                  <Icon className="w-5 h-5 text-blue-600" />
                  <span>{link.label}</span>
                </button>
              );
            })}
            
            <div className="pt-3 mt-2 border-t border-slate-100 flex flex-col gap-2">
              <button
                onClick={() => {
                  setCurrentTab('admin');
                  setMobileMenuOpen(false);
                }}
                className="flex items-center gap-2 text-xs font-bold text-slate-700 hover:text-blue-700 p-2 rounded-lg"
              >
                <LayoutDashboard className="w-4 h-4 text-blue-600" />
                <span>Accès Espace Administrateur</span>
              </button>

              {!isAuthenticated ? (
                <button
                  onClick={() => {
                    openLogin();
                    setMobileMenuOpen(false);
                  }}
                  className="flex items-center justify-center gap-2 text-xs font-bold bg-blue-600 text-white p-2.5 rounded-xl shadow-md"
                >
                  <LogIn className="w-4 h-4" />
                  <span>Se Connecter / Créer un Compte</span>
                </button>
              ) : (
                <button
                  onClick={() => {
                    logout();
                    setMobileMenuOpen(false);
                  }}
                  className="flex items-center justify-center gap-2 text-xs font-bold bg-slate-100 text-red-600 p-2.5 rounded-xl"
                >
                  <LogOut className="w-4 h-4" />
                  <span>Déconnexion ({user.name})</span>
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </header>
  );
};
