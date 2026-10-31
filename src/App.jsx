import React, { useState, useEffect } from 'react';
import { CartProvider, useCart } from './context/CartContext';
import { AuthProvider } from './context/AuthContext';
import { Navbar } from './components/Navbar';
import { Footer } from './components/Footer';
import { CartDrawer } from './components/CartDrawer';
import { CheckoutModal } from './components/CheckoutModal';
import { HomePage } from './pages/HomePage';
import { ParticuliersPage } from './pages/ParticuliersPage';
import { ProfessionnelsPage } from './pages/ProfessionnelsPage';
import { ShopPage } from './pages/ShopPage';
import { OrderTrackingPage } from './pages/OrderTrackingPage';
import { AdminDashboard } from './pages/AdminDashboard';
import { SavingsCalculator } from './components/SavingsCalculator';
import { ReferencesCarousel } from './components/ReferencesCarousel';
import { MessageCircle } from 'lucide-react';

function getTabFromUrl() {
  if (typeof window === 'undefined') return 'home';
  const path = window.location.pathname.replace(/^\/+|\/+$/g, '').toLowerCase();
  const hash = window.location.hash.replace(/^#+/, '').toLowerCase();
  const candidate = path || hash;
  if (['admin', 'particuliers', 'professionnels', 'shop', 'tracking', 'calculator', 'references'].includes(candidate)) {
    return candidate;
  }
  return 'home';
}

function WhatsAppLabel() {
  const { language } = useCart();
  return <span className="hidden sm:inline">{language === 'ar' ? 'كلّم مستشار' : 'Conseiller en Ligne'}</span>;
}

function AppContent() {
  const [currentTab, setCurrentTabState] = useState(getTabFromUrl);
  const [trackingQuery, setTrackingQuery] = useState('');

  const setCurrentTab = (tab) => {
    setCurrentTabState(tab);
    const newPath = tab === 'home' ? '/' : `/${tab}`;
    if (window.location.pathname !== newPath) {
      window.history.pushState(null, '', newPath);
    }
  };

  useEffect(() => {
    const handlePopState = () => {
      setCurrentTabState(getTabFromUrl());
    };
    window.addEventListener('popstate', handlePopState);
    window.addEventListener('hashchange', handlePopState);
    return () => {
      window.removeEventListener('popstate', handlePopState);
      window.removeEventListener('hashchange', handlePopState);
    };
  }, []);

  useEffect(() => {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }, [currentTab]);

  // Si on est dans l'espace administration, afficher UNIQUEMENT le dashboard admin indépendant (sans navbar client, ni bannière, ni footer)
  if (currentTab === 'admin') {
    return <AdminDashboard onExit={() => setCurrentTab('home')} />;
  }

  return (
    <div className="min-h-screen flex flex-col bg-[#f8fafc] text-slate-800 font-sans">
      <Navbar currentTab={currentTab} setCurrentTab={setCurrentTab} />

      <main className="flex-1">
        {currentTab === 'home' && <HomePage setCurrentTab={setCurrentTab} />}
        {currentTab === 'particuliers' && <ParticuliersPage setCurrentTab={setCurrentTab} />}
        {currentTab === 'professionnels' && <ProfessionnelsPage setCurrentTab={setCurrentTab} />}
        {currentTab === 'shop' && <ShopPage />}
        {currentTab === 'tracking' && <OrderTrackingPage initialQuery={trackingQuery} />}
        {currentTab === 'calculator' && (
          <div className="py-12 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-8">
            <div className="text-center max-w-2xl mx-auto">
              <span className="text-xs font-bold text-blue-700 uppercase tracking-wider">Outil d'Aide à la Décision</span>
              <h1 className="text-3xl sm:text-4xl font-black text-slate-900 font-serif mt-1">
                Calculateur d'Économies d'Eau &amp; d'Énergie
              </h1>
              <p className="text-slate-600 text-sm mt-2">
                Simulez vos gains réels en Dinars Tunisiens (DT) selon votre logement ou votre établissement.
              </p>
            </div>
            <SavingsCalculator onSelectPack={() => setCurrentTab('shop')} onRequestAudit={() => setCurrentTab('professionnels')} />
          </div>
        )}
        {currentTab === 'references' && (
          <div className="py-12 space-y-12">
            <ReferencesCarousel />
          </div>
        )}
      </main>

      <CartDrawer />
      <CheckoutModal
        onTrackOrder={(orderId) => {
          setTrackingQuery(orderId);
          setCurrentTab('tracking');
        }}
      />

      <Footer setCurrentTab={setCurrentTab} />

      {/* Floating WhatsApp Action Button - Pure Blue and White */}
      <a
        href="https://wa.me/21698000000?text=Bonjour%20EcoPower%20Tunisie%2C%20je%20souhaite%20des%20informations%20sur%20vos%20produits%20hydro-%C3%A9conomes."
        target="_blank"
        rel="noopener noreferrer"
        aria-label="Contacter EcoPower sur WhatsApp"
        className="fixed bottom-6 right-6 z-50 px-4 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-full flex items-center gap-2 shadow-xl shadow-blue-500/35 hover:scale-105 transition-all duration-200 no-print border border-white/20 font-bold text-xs"
        title="Contacter sur WhatsApp"
      >
        <MessageCircle className="w-5 h-5 text-white" />
        <WhatsAppLabel />
      </a>
    </div>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <CartProvider>
        <AppContent />
      </CartProvider>
    </AuthProvider>
  );
}
