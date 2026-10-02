import express from 'express';
import cors from 'cors';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const PORT = process.env.PORT || 5000;

app.use(cors());
app.use(express.json());

const DATA_DIR = path.join(__dirname, 'data');
const PRODUCTS_FILE = path.join(DATA_DIR, 'products.json');
const ORDERS_FILE = path.join(DATA_DIR, 'orders.json');
const LEADS_FILE = path.join(DATA_DIR, 'leads.json');

// Helper to read JSON
function readJson(filePath, defaultVal = []) {
  try {
    if (!fs.existsSync(filePath)) return defaultVal;
    return JSON.parse(fs.readFileSync(filePath, 'utf-8'));
  } catch (err) {
    console.error(`Error reading ${filePath}:`, err);
    return defaultVal;
  }
}

// Helper to write JSON
function writeJson(filePath, data) {
  try {
    fs.writeFileSync(filePath, JSON.stringify(data, null, 2), 'utf-8');
  } catch (err) {
    console.error(`Error writing ${filePath}:`, err);
  }
}

// ==========================================
// 1. PRODUCTS API
// ==========================================
app.get('/api/products', (req, res) => {
  const products = readJson(PRODUCTS_FILE);
  res.json(products);
});

app.put('/api/products/:id', (req, res) => {
  const { id } = req.params;
  const updates = req.body;
  const products = readJson(PRODUCTS_FILE);
  const index = products.findIndex(p => p.id === id);

  if (index === -1) {
    return res.status(404).json({ error: 'Produit non trouvé' });
  }

  products[index] = { ...products[index], ...updates };
  writeJson(PRODUCTS_FILE, products);
  res.json(products[index]);
});

// ==========================================
// 2. ORDERS API
// ==========================================
app.get('/api/orders', (req, res) => {
  const orders = readJson(ORDERS_FILE);
  res.json(orders);
});

// Helper to generate serial numbers
function generateSerial(productPrefix, index) {
  const year = new Date().getFullYear();
  const rand = Math.floor(1000 + Math.random() * 9000);
  return `SN-${productPrefix.toUpperCase().slice(0, 4)}-${year}-${rand}`;
}

app.post('/api/orders', (req, res) => {
  const { customer, items, paymentMethod = 'cod', notes = '' } = req.body;
  if (!customer || !items || !items.length) {
    return res.status(400).json({ error: 'Données de commande incomplètes' });
  }

  const products = readJson(PRODUCTS_FILE);
  const orders = readJson(ORDERS_FILE);

  let subtotal = 0;
  const enrichedItems = [];

  // Update stock and enrich items with serials
  for (const item of items) {
    const prod = products.find(p => p.id === item.productId);
    const price = prod ? prod.price : item.price;
    const qty = parseInt(item.quantity, 10) || 1;
    subtotal += price * qty;

    // generate serials for each unit
    const serials = [];
    for (let i = 0; i < qty; i++) {
      serials.push(generateSerial(item.productId, i));
    }

    enrichedItems.push({
      productId: item.productId,
      name: prod ? prod.name : item.name,
      price: price,
      quantity: qty,
      serials: serials
    });

    // Deduct stock if available
    if (prod) {
      prod.stock = Math.max(0, (prod.stock || 0) - qty);
    }
  }

  writeJson(PRODUCTS_FILE, products);

  const deliveryFee = subtotal >= 120 ? 0 : 8.0;
  const total = subtotal + deliveryFee;
  const newOrderId = `ECO-${1000 + orders.length + 1}`;
  const certSerial = `CERT-${new Date().getFullYear()}-${newOrderId}`;

  const newOrder = {
    id: newOrderId,
    date: new Date().toISOString(),
    customer: {
      fullName: customer.fullName || '',
      phone: customer.phone || '',
      email: customer.email || '',
      address: customer.address || '',
      city: customer.city || '',
      governorate: customer.governorate || 'Tunis'
    },
    items: enrichedItems,
    subtotal: Math.round(subtotal * 100) / 100,
    deliveryFee: deliveryFee,
    total: Math.round(total * 100) / 100,
    paymentMethod: paymentMethod,
    status: 'pending',
    certificateGenerated: true,
    certificateSerial: certSerial,
    notes: notes || 'Commande passée en ligne'
  };

  orders.unshift(newOrder);
  writeJson(ORDERS_FILE, orders);

  res.status(201).json(newOrder);
});

app.put('/api/orders/:id/status', (req, res) => {
  const { id } = req.params;
  const { status, notes } = req.body;
  const orders = readJson(ORDERS_FILE);
  const order = orders.find(o => o.id === id);

  if (!order) {
    return res.status(404).json({ error: 'Commande non trouvée' });
  }

  if (status) order.status = status;
  if (notes !== undefined) order.notes = notes;

  writeJson(ORDERS_FILE, orders);
  res.json(order);
});

// ==========================================
// 3. CERTIFICATE API
// ==========================================
app.get('/api/certificate/:orderId', (req, res) => {
  const { orderId } = req.params;
  const orders = readJson(ORDERS_FILE);
  const order = orders.find(o => o.id === orderId);

  if (!order) {
    return res.status(404).json({ error: 'Certificat non trouvé pour cette commande' });
  }

  const certData = {
    orderId: order.id,
    certificateSerial: order.certificateSerial || `CERT-2026-${order.id}`,
    issueDate: order.date,
    customerName: order.customer.fullName,
    customerPhone: order.customer.phone,
    customerAddress: `${order.customer.address}, ${order.customer.city} (${order.customer.governorate})`,
    warrantyDuration: '3 ANS (Eco-Sac garanti À VIE)',
    standardConformity: 'Normes Européennes ISO 9001 / ACS Attestation de Conformité Sanitaire / Delrin-Hostaform',
    testedPressure: 'Tenue jusqu’à 25 Bars - Résistant aux chocs thermiques & chlorés',
    items: order.items.map(item => ({
      name: item.name,
      quantity: item.quantity,
      serials: item.serials || []
    })),
    issuer: {
      company: 'ECOPOWER TUNISIE / ECOGAM SARL',
      technicalManager: 'Pascal FABRE & Service Qualité',
      phone: '+216 98 000 000 / eceau-lo@orange.fr',
      officialStamp: 'CERTIFIÉ CONFORME AUX NORMES HYDRO-ÉCONOMIE'
    }
  };

  res.json(certData);
});

// ==========================================
// 4. B2B LEADS API
// ==========================================
app.get('/api/leads', (req, res) => {
  const leads = readJson(LEADS_FILE);
  res.json(leads);
});

app.post('/api/leads', (req, res) => {
  const leadData = req.body;
  const leads = readJson(LEADS_FILE);

  const newLead = {
    id: `LEAD-${200 + leads.length + 1}`,
    date: new Date().toISOString(),
    company: leadData.company || '',
    contactPerson: leadData.contactPerson || '',
    role: leadData.role || '',
    phone: leadData.phone || '',
    email: leadData.email || '',
    type: leadData.type || 'entreprise',
    roomsCount: parseInt(leadData.roomsCount, 10) || 0,
    currentWaterBillMonthly: leadData.currentWaterBillMonthly || '',
    interest: leadData.interest || 'Diagnostic et audit gratuit',
    status: 'new',
    notes: leadData.notes || ''
  };

  leads.unshift(newLead);
  writeJson(LEADS_FILE, leads);
  res.status(201).json(newLead);
});

app.put('/api/leads/:id', (req, res) => {
  const { id } = req.params;
  const { status, notes } = req.body;
  const leads = readJson(LEADS_FILE);
  const lead = leads.find(l => l.id === id);

  if (!lead) {
    return res.status(404).json({ error: 'Demande non trouvée' });
  }

  if (status) lead.status = status;
  if (notes !== undefined) lead.notes = notes;

  writeJson(LEADS_FILE, leads);
  res.json(lead);
});

// Serve public static assets (logos, products)
app.use('/products', express.static(path.join(__dirname, '../public/products')));
app.use('/logos', express.static(path.join(__dirname, '../public/logos')));

// Serve built frontend assets
app.use(express.static(path.join(__dirname, '../dist')));

// Fallback to index.html for SPA routing
app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, '../dist/index.html'));
});

// Start Express
app.listen(PORT, () => {
  console.log(`[ECOPOWER API] Server running on port ${PORT}`);
});

