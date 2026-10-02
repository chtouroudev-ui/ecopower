import React, { useState, useEffect } from 'react';
import { CartProvider } from './context/CartContext';
import { Navbar } from './components/Navbar';
import { Footer } from './components/Footer';
import { CartDrawer } from './components/CartDrawer';
import { CheckoutModal } from './components/CheckoutModal';
import { HomePage } from './pages/HomePage';
import { ParticuliersPage } from './pages/ParticuliersPage';
import { ProfessionnelsPage } from './pages/ProfessionnelsPage';
import { ShopPage } from './pages/ShopPage';
import { AdminDashboard } from './pages/AdminDashboard';
import { SavingsCalculator } from './components/SavingsCalculator';
import { ReferencesCarousel } from './components/ReferencesCarousel';

function AppContent() {
  const [currentTab, setCurrentTab] = useState('home');

  useEffect(() => {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }, [currentTab]);

  return (
    <div className="min-h-screen flex flex-col bg-[#f8fafc] text-slate-800 font-sans">
      <Navbar currentTab={currentTab} setCurrentTab={setCurrentTab} />

      <main className="flex-1">
        {currentTab === 'home' && <HomePage setCurrentTab={setCurrentTab} />}
        {currentTab === 'particuliers' && <ParticuliersPage setCurrentTab={setCurrentTab} />}
        {currentTab === 'professionnels' && <ProfessionnelsPage setCurrentTab={setCurrentTab} />}
        {currentTab === 'shop' && <ShopPage />}
        {currentTab === 'calculator' && (
          <div className="py-12 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-8">
            <div className="text-center max-w-2xl mx-auto">
              <span className="text-xs font-bold text-brand-700 uppercase tracking-wider">Outil d'Aide à la Décision</span>
              <h1 className="text-3xl sm:text-4xl font-black text-slate-900 font-serif mt-1">
                Calculateur d'Économies d'Eau &amp; d'Énergie
              </h1>
              <p className="text-slate-600 text-sm mt-2">
                Simulez vos gains réels en Dinars Tunisiens (DT) selon votre logement ou votre établissement.
              </p>
            </div>
            <SavingsCalculator onSelectPack={(packId) => setCurrentTab('shop')} />
          </div>
        )}
        {currentTab === 'references' && (
          <div className="py-12 space-y-12">
            <ReferencesCarousel />
          </div>
        )}
        {currentTab === 'admin' && <AdminDashboard />}
      </main>

      <CartDrawer />
      <CheckoutModal onOrderPlaced={(order) => {
        console.log('Order confirmed:', order);
      }} />

      <Footer setCurrentTab={setCurrentTab} />

      {/* Floating WhatsApp Button */}
      <a
        href="https://wa.me/21698000000?text=Bonjour%20EcoPower%20Tunisie%2C%20je%20souhaite%20des%20informations%20sur%20vos%20produits%20hydro-%C3%A9conomes."
        target="_blank"
        rel="noopener noreferrer"
        aria-label="Contacter EcoPower sur WhatsApp"
        className="fixed bottom-6 right-6 z-50 w-14 h-14 bg-[#25d366] hover:bg-[#1ebe59] text-white rounded-full flex items-center justify-center shadow-xl shadow-green-500/40 hover:scale-110 transition-all duration-200 no-print"
        title="Contacter sur WhatsApp"
      >
        <svg viewBox="0 0 24 24" className="w-7 h-7 fill-current" xmlns="http://www.w3.org/2000/svg">
          <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z"/>
        </svg>
      </a>
    </div>

  );
}

export default function App() {
  return (
    <CartProvider>
      <AppContent />
    </CartProvider>
  );
}
