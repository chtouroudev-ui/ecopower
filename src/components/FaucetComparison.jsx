import React, { useEffect, useState } from 'react';
import { Droplets, CheckCircle2, AlertTriangle } from 'lucide-react';
import { useCart } from '../context/CartContext';

// 1 minute d'utilisation simulée en 10 secondes réelles
const CYCLE_MS = 10000;
const BASIN_CAPACITY = 24;

const TXT = {
  fr: {
    with: 'Avec EcoPower',
    without: 'Sans EcoPower',
    liters: 'Litres consommés',
    perYear: 'Par an (10 min/jour)',
    badge: 'Démonstration en direct',
    title: "Le même robinet, une minute d'utilisation",
    text: (before, after) => `Sans régulateur, la pression SONEDE fait couler jusqu'à ${before} L/min. Avec un hydro-économe EcoPower, le confort reste le même pour seulement ${after} L/min.`,
    saved: (pct) => `-${pct}% d'eau consommée, et autant de gaz économisé pour la chauffer`,
  },
  ar: {
    with: 'مع EcoPower',
    without: 'بلا EcoPower',
    liters: 'اللترات المستهلكة',
    perYear: 'في العام (10 دقايق في النهار)',
    badge: 'تجربة مباشرة',
    title: 'نفس الروبيني، دقيقة استعمال',
    text: (before, after) => `بلا منظّم، ضغط الصوناد يخلّي الماء يصب حتى لـ ${before} لتر في الدقيقة. مع موفّر EcoPower، تبقى نفس الراحة وتستهلك كان ${after} لتر في الدقيقة.`,
    saved: (pct) => `-${pct}% في الماء، وقد قدّو توفير في الغاز اللي يسخّنو`,
  },
};

const Faucet = ({ rate, variant, t }) => {
  const isEco = variant === 'eco';
  const [liters, setLiters] = useState(0);

  useEffect(() => {
    const start = performance.now();
    let frame;
    const tick = (now) => {
      const progress = ((now - start) % CYCLE_MS) / CYCLE_MS;
      setLiters(rate * progress);
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [rate]);

  const streamWidth = isEco ? 6 : 26;
  const fill = Math.min(liters / BASIN_CAPACITY, 1);
  const basinTop = 196;
  const basinHeight = 70;
  const waterHeight = basinHeight * fill;
  const drops = isEco ? 3 : 12;
  const color = isEco ? '#0ea5e9' : '#3b82f6';

  return (
    <div className={`rounded-2xl p-5 sm:p-6 border-2 ${isEco ? 'border-blue-300 bg-gradient-to-b from-sky-50 to-white' : 'border-red-200 bg-gradient-to-b from-red-50 to-white'}`}>
      <div className="flex items-center justify-between mb-3">
        <span className={`inline-flex items-center gap-1.5 text-xs font-black uppercase tracking-wider px-3 py-1 rounded-full ${isEco ? 'bg-blue-600 text-white' : 'bg-red-100 text-red-700'}`}>
          {isEco ? <CheckCircle2 className="w-3.5 h-3.5" /> : <AlertTriangle className="w-3.5 h-3.5" />}
          {isEco ? t.with : t.without}
        </span>
        <span dir="ltr" className={`text-sm font-extrabold ${isEco ? 'text-blue-700' : 'text-red-600'}`}>{rate} L/min</span>
      </div>

      <svg viewBox="0 0 220 280" className="w-full max-w-[260px] mx-auto block" aria-hidden="true">
        <defs>
          <linearGradient id={`chrome-${variant}`} x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor="#e2e8f0" />
            <stop offset="50%" stopColor="#94a3b8" />
            <stop offset="100%" stopColor="#64748b" />
          </linearGradient>
          <linearGradient id={`stream-${variant}`} x1="0" x2="1">
            <stop offset="0%" stopColor={color} stopOpacity="0.55" />
            <stop offset="50%" stopColor={color} stopOpacity="0.95" />
            <stop offset="100%" stopColor={color} stopOpacity="0.55" />
          </linearGradient>
          <clipPath id={`basin-${variant}`}>
            <path d={`M30 ${basinTop} H190 L178 ${basinTop + basinHeight} H42 Z`} />
          </clipPath>
        </defs>

        {/* Mur + tuyau */}
        <rect x="0" y="20" width="22" height="70" rx="4" fill="#cbd5e1" />
        <rect x="18" y="38" width="80" height="22" rx="8" fill={`url(#chrome-${variant})`} />
        <rect x="72" y="18" width="22" height="20" rx="4" fill={`url(#chrome-${variant})`} />
        <rect x="62" y="12" width="42" height="9" rx="4" fill="#475569" />
        {/* Bec */}
        <path d="M90 38 H128 Q140 38 140 52 V78 H118 V60 H90 Z" fill={`url(#chrome-${variant})`} />
        <rect x="114" y="76" width="30" height="8" rx="3" fill={isEco ? '#2563eb' : '#64748b'} />
        {isEco && <text x="129" y="83" textAnchor="middle" fontSize="6" fontWeight="800" fill="#fff">ECO</text>}

        {/* Jet d'eau */}
        <g className={isEco ? 'faucet-stream faucet-stream-slow' : 'faucet-stream'}>
          <rect
            x={129 - streamWidth / 2}
            y="84"
            width={streamWidth}
            height={basinTop + basinHeight - waterHeight - 84}
            fill={`url(#stream-${variant})`}
            rx={streamWidth / 2}
          />
        </g>
        <rect
          x={129 - streamWidth / 2}
          y="84"
          width={streamWidth}
          height={basinTop + basinHeight - waterHeight - 84}
          fill="url(#stripes)"
          opacity="0.35"
        />

        {/* Gouttes / éclaboussures */}
        {Array.from({ length: drops }).map((_, i) => (
          <circle
            key={i}
            cx={129 + (i % 2 === 0 ? -1 : 1) * (streamWidth / 2 + 4 + (i * 7) % 26)}
            cy={basinTop + basinHeight - waterHeight - 4}
            r={isEco ? 1.6 : 2.6}
            fill={color}
            className="faucet-splash"
            style={{ animationDelay: `${(i * 0.13) % 0.9}s`, '--dx': `${(i % 2 === 0 ? -1 : 1) * (8 + (i * 5) % 18)}px` }}
          />
        ))}

        {/* Bassin + niveau d'eau */}
        <g clipPath={`url(#basin-${variant})`}>
          <rect x="20" y={basinTop} width="180" height={basinHeight} fill="#f1f5f9" />
          <rect x="20" y={basinTop + basinHeight - waterHeight} width="180" height={waterHeight} fill={color} opacity="0.75" />
          <path
            className="faucet-wave"
            d={`M0 ${basinTop + basinHeight - waterHeight} q10 -4 20 0 t20 0 t20 0 t20 0 t20 0 t20 0 t20 0 t20 0 t20 0 t20 0 t20 0 t20 0 v6 H0 Z`}
            fill="#ffffff"
            opacity="0.35"
          />
        </g>
        <path d={`M24 ${basinTop - 4} H196 L182 ${basinTop + basinHeight + 4} H38 Z`} fill="none" stroke="#94a3b8" strokeWidth="4" strokeLinejoin="round" />
      </svg>

      <div className="mt-4 grid grid-cols-2 gap-3 text-center">
        <div className="bg-white rounded-xl border border-slate-200 p-3">
          <div className="text-[10px] uppercase font-bold text-slate-500 tracking-wider">{t.liters}</div>
          <div className={`text-2xl font-black tabular-nums ${isEco ? 'text-blue-700' : 'text-red-600'}`}>{liters.toFixed(1)} L</div>
        </div>
        <div className="bg-white rounded-xl border border-slate-200 p-3">
          <div className="text-[10px] uppercase font-bold text-slate-500 tracking-wider">{t.perYear}</div>
          <div className={`text-2xl font-black tabular-nums ${isEco ? 'text-blue-700' : 'text-red-600'}`}>{Math.round(rate * 10 * 365 / 1000)} m³</div>
        </div>
      </div>
    </div>
  );
};

export const FaucetComparison = () => {
  const { language } = useCart();
  const t = TXT[language] || TXT.fr;
  const before = 22;
  const after = 4;
  const saved = Math.round((1 - after / before) * 100);

  return (
    <div className="bg-white rounded-3xl p-6 sm:p-10 border border-slate-200 shadow-md space-y-6">
      <svg width="0" height="0" className="absolute">
        <defs>
          <pattern id="stripes" width="8" height="16" patternUnits="userSpaceOnUse">
            <rect width="8" height="6" fill="#ffffff" />
            <animateTransform attributeName="patternTransform" type="translate" from="0 0" to="0 16" dur="0.35s" repeatCount="indefinite" />
          </pattern>
        </defs>
      </svg>

      <div className="text-center max-w-2xl mx-auto space-y-2">
        <div className="inline-flex items-center gap-2 text-blue-700 bg-blue-50 px-3 py-1 rounded-md text-xs font-bold">
          <Droplets className="w-4 h-4" />
          <span>{t.badge}</span>
        </div>
        <h2 className="text-2xl sm:text-3xl font-extrabold text-slate-900 font-serif">
          {t.title}
        </h2>
        <p className="text-slate-600 text-sm">
          {t.text(before, after)}
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Faucet rate={before} variant="raw" t={t} />
        <Faucet rate={after} variant="eco" t={t} />
      </div>

      <div className="text-center">
        <span className="inline-block px-5 py-2.5 rounded-full bg-gradient-to-r from-blue-600 to-sky-500 text-white font-black text-sm sm:text-base shadow-md">
          {t.saved(saved)}
        </span>
      </div>
    </div>
  );
};
