/**
 * Moteur de calcul du simulateur EcoPower (formules fournies par EcoPower).
 *
 * 1. Chauffage gaz STEG :   ChauffageCost(V, ΔT) = V × ΔT / 860 × PrixGaz
 * 2. Volumes par point d'usage (douche, lavabo, flexible WC, chasse WC)
 * 3. Facture SONEDE : volume trimestriel (90 j), tarif de la tranche atteinte
 *    appliqué à la totalité du volume, ramené au jour.
 * 4. Investissement hôtel = Nchambres × (Plav + Pdouche + Pflex)
 * 5. Économies jour / mois (×30) / an (×12) et ROI = Investissement / Économie.
 */

export const T_FROIDE = 18; // °C
export const T_USAGE = { douche: 38, lavabo: 35, cuisine: 45 };
export const KCAL_PAR_KWH = 860;
export const PRIX_GAZ = 0.026; // DT/kWh (STEG 1ère tranche)

export const SONEDE_TRANCHES = [
  { max: 20, tarif: 0.2, label: '≤ 20 m³' },
  { max: 40, tarif: 0.74, label: '20 à 40 m³' },
  { max: 70, tarif: 1.04, label: '40 à 70 m³' },
  { max: 100, tarif: 1.49, label: '70 à 100 m³' },
  { max: 150, tarif: 1.77, label: '100 à 150 m³' },
  { max: Infinity, tarif: 2.31, label: '> 150 m³' },
];

// Tarifs unitaires hôtel (DT)
export const PRIX_HOTEL = {
  lavabo: { 2: 20.2, 3: 19.5 },
  douche: 22.9,
  flex: 22.9,
};

export const deltaT = (usage) => (usage in T_USAGE ? T_USAGE[usage] - T_FROIDE : 0);

/** Coût (DT) du chauffage au gaz de `litres` d'eau mitigée élevée de `dT` °C. */
export function chauffageCost(litres, dT) {
  return ((litres * dT) / KCAL_PAR_KWH) * PRIX_GAZ;
}

export const kwh = (litres, dT) => (litres * dT) / KCAL_PAR_KWH;

export function trancheSonede(m3Trim) {
  return SONEDE_TRANCHES.find((t) => m3Trim <= t.max);
}

/** Coût de l'eau par jour (DT) pour un volume journalier en litres. */
export function coutEauJour(litresJour) {
  const vTrim = (litresJour * 90) / 1000;
  const tranche = trancheSonede(vTrim);
  return { vTrim, tranche, cout: (vTrim * tranche.tarif) / 90 };
}

/**
 * Agrège une liste de points d'usage { key, label, sans, avec, dT } (litres/jour)
 * en coûts eau + gaz journaliers et économies.
 */
export function bilan(points, investissement) {
  const vSans = points.reduce((s, p) => s + p.sans, 0);
  const vAvec = points.reduce((s, p) => s + p.avec, 0);
  const eauSans = coutEauJour(vSans);
  const eauAvec = coutEauJour(vAvec);
  const gazSans = points.reduce((s, p) => s + chauffageCost(p.sans, p.dT), 0);
  const gazAvec = points.reduce((s, p) => s + chauffageCost(p.avec, p.dT), 0);
  const kwhSans = points.reduce((s, p) => s + kwh(p.sans, p.dT), 0);
  const kwhAvec = points.reduce((s, p) => s + kwh(p.avec, p.dT), 0);

  const totalSans = eauSans.cout + gazSans;
  const totalAvec = eauAvec.cout + gazAvec;
  const ecoJour = Math.max(0, totalSans - totalAvec);
  const ecoMois = ecoJour * 30;
  const ecoAn = ecoMois * 12;

  return {
    points,
    vSans,
    vAvec,
    eauSans,
    eauAvec,
    gazSans,
    gazAvec,
    kwhSans,
    kwhAvec,
    totalSans,
    totalAvec,
    ecoJour,
    ecoMois,
    ecoAn,
    ecoEauJour: eauSans.cout - eauAvec.cout,
    ecoGazJour: gazSans - gazAvec,
    m3EconomisesAn: ((vSans - vAvec) * 360) / 1000,
    kwhEconomisesAn: (kwhSans - kwhAvec) * 360,
    pourcentage: vSans > 0 ? ((vSans - vAvec) / vSans) * 100 : 0,
    investissement,
    roiJours: ecoJour > 0 ? investissement / ecoJour : Infinity,
    roiMois: ecoMois > 0 ? investissement / ecoMois : Infinity,
  };
}

/** Simulation hôtel : périmètre restreint aux chambres. */
export function simulerHotel(p) {
  const clientsJour = p.chambres * (p.occupation / 100) * p.personnesParChambre;
  const dTd = deltaT('douche');
  const dTl = deltaT('lavabo');

  const points = [
    {
      key: 'douche',
      label: 'Douche',
      detail: `${p.dIniDouche} → ${p.dEcoDouche} L/min`,
      sans: p.dIniDouche * p.tDouche * clientsJour,
      avec: p.dEcoDouche * p.tDouche * clientsJour,
      dT: dTd,
    },
    {
      key: 'lavabo',
      label: 'Lavabo',
      detail: `${p.dIniLavabo} → ${p.dEcoLavabo} L/min`,
      sans: p.dIniLavabo * p.tLavabo * p.freqLavabo * clientsJour,
      avec: p.dEcoLavabo * p.tLavabo * p.freqLavabo * clientsJour,
      dT: dTl,
    },
  ];

  const dIniFlex = 12;
  const vFlexSans = dIniFlex * p.tFlex * p.freqFlex * clientsJour;
  points.push({
    key: 'flex',
    label: 'Flexible toilette',
    detail: p.dEcoFlex ? `${dIniFlex} → ${p.dEcoFlex} L/min` : 'Sans économiseur',
    sans: vFlexSans,
    avec: p.dEcoFlex ? p.dEcoFlex * p.tFlex * p.freqFlex * clientsJour : vFlexSans,
    dT: 0,
  });

  if (p.ecoSac) {
    points.push({
      key: 'wc',
      label: 'Chasse WC (Eco-Sac)',
      detail: `${p.chasseLitres} → ${p.chasseLitres - 3} L/chasse`,
      sans: p.chasseLitres * p.chassesParClient * clientsJour,
      avec: (p.chasseLitres - 3) * p.chassesParClient * clientsJour,
      dT: 0,
    });
  }

  const prixLav = PRIX_HOTEL.lavabo[p.dEcoLavabo] ?? PRIX_HOTEL.lavabo[3];
  const prixFlex = p.dEcoFlex ? PRIX_HOTEL.flex : 0;
  const prixEcoSac = p.ecoSac ? p.prixEcoSac : 0;
  const coutChambre = prixLav + PRIX_HOTEL.douche + prixFlex + prixEcoSac;
  const investissement = p.chambres * coutChambre;

  return {
    clientsJour,
    coutChambre,
    prixLav,
    prixFlex,
    prixEcoSac,
    ...bilan(points, investissement),
  };
}

/** Simulation particulier : mêmes formules, appliquées aux personnes du foyer. */
export function simulerFoyer(p) {
  const n = p.personnes;
  const points = [
    {
      key: 'douche',
      label: 'Douche',
      detail: `${p.dIniDouche} → ${p.dEcoDouche} L/min`,
      sans: p.dIniDouche * p.tDouche * n,
      avec: p.dEcoDouche * p.tDouche * n,
      dT: deltaT('douche'),
    },
    {
      key: 'lavabo',
      label: 'Lavabo',
      detail: `${p.dIniRobinet} → ${p.dEcoRobinet} L/min`,
      sans: p.dIniRobinet * p.tLavabo * n,
      avec: p.dEcoRobinet * p.tLavabo * n,
      dT: deltaT('lavabo'),
    },
    {
      key: 'cuisine',
      label: 'Évier cuisine',
      detail: `${p.dIniRobinet} → ${p.dEcoRobinet} L/min`,
      sans: p.dIniRobinet * p.tCuisine,
      avec: p.dEcoRobinet * p.tCuisine,
      dT: deltaT('cuisine'),
    },
    {
      key: 'wc',
      label: 'Chasse WC (Eco-Sac)',
      detail: '10 → 7 L/chasse',
      sans: 10 * p.chasses * n,
      avec: 7 * p.chasses * n,
      dT: 0,
    },
  ];
  return bilan(points, p.prixPack);
}

export const fmt = (n, d = 0) =>
  Number.isFinite(n)
    ? n.toLocaleString('fr-FR', { minimumFractionDigits: d, maximumFractionDigits: d })
    : '—';
