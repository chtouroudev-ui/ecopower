import express from 'express';
import cors from 'cors';
import path from 'path';
import { fileURLToPath } from 'url';
import jwt from 'jsonwebtoken';
import bcrypt from 'bcryptjs';
import dotenv from 'dotenv';
import { pool, initDb } from './db.js';

dotenv.config();

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const PORT = process.env.PORT || 5000;
const JWT_SECRET = process.env.JWT_SECRET || 'ecopower_secret_jwt_key_2026_tunisie';

// ── Security Headers ──
app.use((req, res, next) => {
  res.setHeader('X-Content-Type-Options', 'nosniff');
  res.setHeader('X-Frame-Options', 'SAMEORIGIN');
  res.setHeader('X-XSS-Protection', '1; mode=block');
  res.setHeader('Referrer-Policy', 'strict-origin-when-cross-origin');
  res.removeHeader('X-Powered-By');
  next();
});

// ── Strict CORS Policy ──
const allowedOrigins = process.env.ALLOWED_ORIGINS
  ? process.env.ALLOWED_ORIGINS.split(',').map(s => s.trim())
  : ['http://localhost:5173', 'http://localhost:3000', 'http://localhost:5000'];

app.use(cors({
  origin: (origin, callback) => {
    if (!origin || allowedOrigins.includes(origin) || process.env.NODE_ENV !== 'production') {
      return callback(null, true);
    }
    return callback(new Error('Non autorisé par la politique CORS'));
  },
  credentials: true,
}));

app.use(express.json({ limit: '1mb' }));

// ── In-Memory Rate Limiter ──
function createRateLimiter({ windowMs = 15 * 60 * 1000, max = 100, message = 'Trop de requêtes, veuillez réessayer plus tard.' } = {}) {
  const requests = new Map();
  setInterval(() => {
    const now = Date.now();
    for (const [ip, data] of requests.entries()) {
      if (now > data.resetTime) requests.delete(ip);
    }
  }, Math.min(windowMs, 60000)).unref();

  return (req, res, next) => {
    const ip = req.ip || req.headers['x-forwarded-for'] || req.socket?.remoteAddress || 'unknown';
    const now = Date.now();
    let record = requests.get(ip);
    if (!record || now > record.resetTime) {
      record = { count: 1, resetTime: now + windowMs };
      requests.set(ip, record);
    } else {
      record.count++;
    }

    if (record.count > max) {
      return res.status(429).json({ error: message });
    }
    next();
  };
}

const authLimiter = createRateLimiter({ windowMs: 15 * 60 * 1000, max: 20, message: 'Trop de tentatives de connexion. Veuillez patienter 15 minutes.' });
const orderLimiter = createRateLimiter({ windowMs: 10 * 60 * 1000, max: 20, message: 'Trop de requêtes de commande. Veuillez patienter quelques minutes.' });
const trackingLimiter = createRateLimiter({ windowMs: 5 * 60 * 1000, max: 40, message: 'Trop de recherches de commande. Veuillez patienter.' });


// Helper to generate serial numbers
function generateSerial(productPrefix, index) {
  const year = new Date().getFullYear();
  const rand = Math.floor(1000 + Math.random() * 9000);
  const cleanPrefix = (productPrefix || 'PROD').toUpperCase().replace(/[^A-Z0-9]/g, '').slice(0, 4);
  return `SN-${cleanPrefix}-${year}-${rand}`;
}

// Auth Middleware
function authenticateToken(req, res, next) {
  const authHeader = req.headers['authorization'];
  const token = authHeader && authHeader.split(' ')[1];

  if (!token) {
    return res.status(401).json({ error: 'Accès non autorisé: token requis' });
  }

  jwt.verify(token, JWT_SECRET, (err, decoded) => {
    if (err) {
      return res.status(403).json({ error: 'Token invalide ou expiré' });
    }
    req.user = decoded;
    next();
  });
}

function requireAdmin(req, res, next) {
  if (!req.user || req.user.role !== 'admin') {
    return res.status(403).json({ error: 'Accès refusé: privilèges administrateur requis' });
  }
  next();
}

// ==========================================
// 1. AUTH API
// ==========================================

// Login
app.post('/api/auth/login', authLimiter, async (req, res) => {
  try {
    const { email, password } = req.body;
    if (!email || !password) {
      return res.status(400).json({ error: 'Email et mot de passe requis' });
    }

    const [rows] = await pool.query('SELECT * FROM users WHERE email = ?', [email.trim().toLowerCase()]);
    if (rows.length === 0) {
      return res.status(401).json({ error: 'Email ou mot de passe incorrect' });
    }

    const dbUser = rows[0];
    const match = await bcrypt.compare(password, dbUser.password);
    if (!match || dbUser.role !== 'admin') {
      return res.status(401).json({ error: 'Email ou mot de passe incorrect' });
    }

    const user = {
      id: dbUser.id,
      name: dbUser.name,
      email: dbUser.email,
      role: dbUser.role,
      phone: dbUser.phone,
    };

    const token = jwt.sign(user, JWT_SECRET, { expiresIn: '7d' });
    res.json({ message: 'Connexion réussie', token, user });
  } catch (error) {
    console.error('Login error:', error);
    res.status(500).json({ error: 'Erreur lors de la connexion' });
  }
});

// Get current user profile
app.get('/api/auth/me', authenticateToken, async (req, res) => {
  try {
    const [rows] = await pool.query('SELECT id, name, email, role, phone, created_at FROM users WHERE id = ?', [req.user.id]);
    if (rows.length === 0) {
      return res.status(404).json({ error: 'Utilisateur introuvable' });
    }
    res.json({ user: rows[0] });
  } catch (error) {
    console.error('Get profile error:', error);
    res.status(500).json({ error: 'Erreur serveur' });
  }
});

// ==========================================
// 2. PRODUCTS API
// ==========================================

// Get all products
app.get('/api/products', async (req, res) => {
  try {
    const [rows] = await pool.query('SELECT * FROM products ORDER BY is_featured DESC, price ASC');
    const products = rows.map(p => ({
      id: p.id,
      name: p.name,
      nameAr: p.name_ar,
      category: p.category,
      price: parseFloat(p.price),
      oldPrice: p.old_price ? parseFloat(p.old_price) : null,
      rating: parseFloat(p.rating),
      reviewsCount: p.reviews_count,
      warranty: p.warranty,
      debit: p.debit,
      image: p.image,
      description: p.description,
      features: typeof p.features === 'string' ? JSON.parse(p.features) : (p.features || []),
      stock: p.stock,
      isFeatured: Boolean(p.is_featured),
    }));
    res.json(products);
  } catch (error) {
    console.error('Get products error:', error);
    res.status(500).json({ error: 'Erreur lors de la récupération des produits' });
  }
});

// Get single product
app.get('/api/products/:id', async (req, res) => {
  try {
    const { id } = req.params;
    const [rows] = await pool.query('SELECT * FROM products WHERE id = ?', [id]);
    if (rows.length === 0) {
      return res.status(404).json({ error: 'Produit non trouvé' });
    }
    const p = rows[0];
    res.json({
      id: p.id,
      name: p.name,
      nameAr: p.name_ar,
      category: p.category,
      price: parseFloat(p.price),
      oldPrice: p.old_price ? parseFloat(p.old_price) : null,
      rating: parseFloat(p.rating),
      reviewsCount: p.reviews_count,
      warranty: p.warranty,
      debit: p.debit,
      image: p.image,
      description: p.description,
      features: typeof p.features === 'string' ? JSON.parse(p.features) : (p.features || []),
      stock: p.stock,
      isFeatured: Boolean(p.is_featured),
    });
  } catch (error) {
    console.error('Get product error:', error);
    res.status(500).json({ error: 'Erreur serveur' });
  }
});

// Add new product (admin)
app.post('/api/products', authenticateToken, requireAdmin, async (req, res) => {
  try {
    const p = req.body;
    const id = p.id || `prod-${Date.now()}`;
    await pool.query(
      `INSERT INTO products (id, name, name_ar, category, price, old_price, rating, reviews_count, warranty, debit, image, description, features, stock, is_featured)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      [
        id,
        p.name,
        p.nameAr || null,
        p.category || 'packs',
        p.price || 0,
        p.oldPrice || null,
        p.rating || 5,
        p.reviewsCount || 0,
        p.warranty || '3 ans',
        p.debit || null,
        p.image || '/products/bague_mousseur_complet.jpg',
        p.description || '',
        JSON.stringify(p.features || []),
        p.stock !== undefined ? p.stock : 50,
        p.isFeatured ? 1 : 0
      ]
    );

    res.status(201).json({ id, ...p });
  } catch (error) {
    console.error('Create product error:', error);
    res.status(500).json({ error: 'Erreur création produit' });
  }
});

// Update product (admin)
app.put('/api/products/:id', authenticateToken, requireAdmin, async (req, res) => {
  try {
    const { id } = req.params;
    const updates = req.body;

    const fields = [];
    const values = [];

    if (updates.name !== undefined) { fields.push('name = ?'); values.push(updates.name); }
    if (updates.nameAr !== undefined) { fields.push('name_ar = ?'); values.push(updates.nameAr); }
    if (updates.category !== undefined) { fields.push('category = ?'); values.push(updates.category); }
    if (updates.price !== undefined) { fields.push('price = ?'); values.push(updates.price); }
    if (updates.oldPrice !== undefined) { fields.push('old_price = ?'); values.push(updates.oldPrice); }
    if (updates.stock !== undefined) { fields.push('stock = ?'); values.push(updates.stock); }
    if (updates.warranty !== undefined) { fields.push('warranty = ?'); values.push(updates.warranty); }
    if (updates.debit !== undefined) { fields.push('debit = ?'); values.push(updates.debit); }
    if (updates.description !== undefined) { fields.push('description = ?'); values.push(updates.description); }
    if (updates.features !== undefined) { fields.push('features = ?'); values.push(JSON.stringify(updates.features)); }
    if (updates.image !== undefined) { fields.push('image = ?'); values.push(updates.image); }
    if (updates.isFeatured !== undefined) { fields.push('is_featured = ?'); values.push(updates.isFeatured ? 1 : 0); }

    if (fields.length === 0) {
      return res.status(400).json({ error: 'Aucun champ à mettre à jour' });
    }

    values.push(id);
    const [result] = await pool.query(`UPDATE products SET ${fields.join(', ')} WHERE id = ?`, values);

    if (result.affectedRows === 0) {
      return res.status(404).json({ error: 'Produit non trouvé' });
    }

    const [updated] = await pool.query('SELECT * FROM products WHERE id = ?', [id]);
    res.json(updated[0]);
  } catch (error) {
    console.error('Update product error:', error);
    res.status(500).json({ error: 'Erreur mise à jour produit' });
  }
});

// Delete product (admin)
app.delete('/api/products/:id', authenticateToken, requireAdmin, async (req, res) => {
  try {
    const { id } = req.params;
    const [result] = await pool.query('DELETE FROM products WHERE id = ?', [id]);
    if (result.affectedRows === 0) {
      return res.status(404).json({ error: 'Produit non trouvé' });
    }
    res.json({ message: 'Produit supprimé avec succès' });
  } catch (error) {
    console.error('Delete product error:', error);
    res.status(500).json({ error: 'Erreur lors de la suppression' });
  }
});

// ==========================================
// 3. ORDERS API
// ==========================================

// Get all orders (admin only)
app.get('/api/orders', authenticateToken, requireAdmin, async (req, res) => {
  try {
    const [orders] = await pool.query('SELECT * FROM orders ORDER BY created_at DESC');
    const [items] = await pool.query('SELECT * FROM order_items');

    const formattedOrders = orders.map(o => {
      const orderItems = items
        .filter(i => i.order_id === o.id)
        .map(i => ({
          id: i.id,
          productId: i.product_id,
          name: i.name,
          price: parseFloat(i.price),
          quantity: i.quantity,
          serials: typeof i.serials === 'string' ? JSON.parse(i.serials) : (i.serials || []),
        }));

      return {
        id: o.id,
        date: o.created_at,
        customer: {
          fullName: o.customer_name,
          phone: o.customer_phone,
          email: o.customer_email || '',
          address: o.customer_address || '',
          city: o.customer_city || '',
          governorate: o.customer_governorate || 'Tunis',
        },
        items: orderItems,
        subtotal: parseFloat(o.subtotal),
        deliveryFee: parseFloat(o.delivery_fee),
        total: parseFloat(o.total),
        paymentMethod: o.payment_method,
        status: o.status,
        certificateGenerated: Boolean(o.certificate_serial),
        certificateSerial: o.certificate_serial,
        notes: o.notes || '',
      };
    });

    res.json(formattedOrders);
  } catch (error) {
    console.error('Get orders error:', error);
    res.status(500).json({ error: 'Erreur lors de la récupération des commandes' });
  }
});

// Public Track Order (by Order ID or Phone number, rate limited)
app.get('/api/orders/track/:query', trackingLimiter, async (req, res) => {
  try {
    const { query } = req.params;
    let cleanQuery = query.trim().toUpperCase();
    const digits = cleanQuery.replace(/[^0-9]/g, '').replace(/^216/, '');
    if (/^[0-9\s+]+$/.test(cleanQuery) && digits.length === 8) cleanQuery = digits;

    const [orders] = await pool.query(
      'SELECT * FROM orders WHERE id = ? OR customer_phone = ? ORDER BY created_at DESC LIMIT 5',
      [cleanQuery, cleanQuery]
    );

    if (orders.length === 0) {
      return res.status(404).json({ error: 'Aucune commande trouvée avec cette référence ou ce numéro de téléphone.' });
    }

    const orderIds = orders.map(o => o.id);
    const [items] = await pool.query(
      'SELECT * FROM order_items WHERE order_id IN (?)',
      [orderIds]
    );

    const formatted = orders.map(o => ({
      id: o.id,
      date: o.created_at,
      customerName: o.customer_name,
      customerPhone: o.customer_phone,
      governorate: o.customer_governorate,
      items: items.filter(i => i.order_id === o.id).map(i => ({
        name: i.name,
        quantity: i.quantity,
        price: parseFloat(i.price),
        serials: typeof i.serials === 'string' ? JSON.parse(i.serials) : (i.serials || []),
      })),
      total: parseFloat(o.total),
      deliveryFee: parseFloat(o.delivery_fee),
      status: o.status,
      paymentMethod: o.payment_method,
      certificateSerial: o.certificate_serial,
    }));

    res.json(formatted);
  } catch (error) {
    console.error('Track order error:', error);
    res.status(500).json({ error: 'Erreur lors du suivi de commande' });
  }
});

// Create Order (public checkout, rate limited)
app.post('/api/orders', orderLimiter, async (req, res) => {
  const { customer, items, notes = '' } = req.body || {};
  const phone = String(customer?.phone || '').replace(/[^0-9]/g, '').replace(/^216/, '');
  if (!customer?.fullName?.trim() || !customer?.address?.trim() || !Array.isArray(items) || !items.length) {
    return res.status(400).json({ error: 'Veuillez renseigner votre nom, votre adresse et au moins un article.' });
  }
  if (!/^[2-9][0-9]{7}$/.test(phone)) {
    return res.status(400).json({ error: 'Numéro de téléphone invalide (8 chiffres attendus).' });
  }
  customer.phone = phone;
  // Les acheteurs n'ont pas de compte : paiement uniquement à la livraison
  const paymentMethod = 'cod';

  const connection = await pool.getConnection();
  try {
    await connection.beginTransaction();

    // 1. Get current count to generate next ID
    const [lastRows] = await connection.query(
      "SELECT MAX(CAST(SUBSTRING(id, 5) AS UNSIGNED)) AS lastNum FROM orders WHERE id LIKE 'ECO-%' FOR UPDATE"
    );
    const newOrderId = `ECO-${Math.max(1000, lastRows[0].lastNum || 0) + 1}`;
    const certSerial = `CERT-${new Date().getFullYear()}-${newOrderId}`;

    let subtotal = 0;
    const enrichedItems = [];

    // 2. Process items, verify prices, decrement stock, generate serials
    for (const item of items) {
      const [prodRows] = await connection.query('SELECT * FROM products WHERE id = ?', [item.productId]);
      const prod = prodRows[0];
      if (!prod) {
        throw Object.assign(new Error('Produit indisponible'), { status: 400, publicMessage: `Le produit « ${item.name || item.productId} » n'est plus disponible.` });
      }

      const price = parseFloat(prod.price);
      const qty = Math.min(99, Math.max(1, parseInt(item.quantity, 10) || 1));
      subtotal += price * qty;

      const serials = [];
      for (let i = 0; i < qty; i++) {
        serials.push(generateSerial(item.productId, i));
      }

      enrichedItems.push({
        productId: item.productId,
        name: prod.name,
        price: price,
        quantity: qty,
        serials: serials,
      });

      // Deduct stock in DB
      await connection.query(
        'UPDATE products SET stock = GREATEST(0, stock - ?) WHERE id = ?',
        [qty, item.productId]
      );
    }

    const deliveryFee = subtotal >= 120 ? 0 : 8.0;
    const total = subtotal + deliveryFee;
    const userId = null;

    // 3. Insert order
    await connection.query(
      `INSERT INTO orders 
       (id, user_id, customer_name, customer_phone, customer_email, customer_address, customer_city, customer_governorate, subtotal, delivery_fee, total, payment_method, status, certificate_serial, notes)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      [
        newOrderId,
        userId,
        customer.fullName.trim().slice(0, 150),
        customer.phone,
        customer.email || null,
        customer.address || '',
        customer.city || '',
        customer.governorate || 'Tunis',
        subtotal,
        deliveryFee,
        total,
        paymentMethod,
        'pending',
        certSerial,
        String(notes || '').slice(0, 1000),
      ]
    );

    // 4. Insert order items
    for (const item of enrichedItems) {
      await connection.query(
        `INSERT INTO order_items (order_id, product_id, name, price, quantity, serials)
         VALUES (?, ?, ?, ?, ?, ?)`,
        [
          newOrderId,
          item.productId,
          item.name,
          item.price,
          item.quantity,
          JSON.stringify(item.serials),
        ]
      );
    }

    await connection.commit();
    connection.release();

    const createdOrder = {
      id: newOrderId,
      date: new Date().toISOString(),
      customer: customer,
      items: enrichedItems,
      subtotal: Math.round(subtotal * 100) / 100,
      deliveryFee: deliveryFee,
      total: Math.round(total * 100) / 100,
      paymentMethod: paymentMethod,
      status: 'pending',
      certificateGenerated: true,
      certificateSerial: certSerial,
      notes: notes,
    };

    res.status(201).json(createdOrder);
  } catch (error) {
    await connection.rollback();
    connection.release();
    if (error.publicMessage) {
      return res.status(error.status || 400).json({ error: error.publicMessage });
    }
    console.error('Create order error:', error);
    res.status(500).json({ error: 'Erreur lors de la validation de la commande' });
  }
});

// Update order status (admin)
const ORDER_STATUSES = ['pending', 'confirmed', 'shipped', 'delivered', 'cancelled'];

const handleOrderUpdate = async (req, res) => {
  const { id } = req.params;
  const { status, notes } = req.body || {};

  if (status !== undefined && !ORDER_STATUSES.includes(status)) {
    return res.status(400).json({ error: 'Statut de commande invalide' });
  }
  if (status === undefined && notes === undefined) {
    return res.status(400).json({ error: 'Aucune donnée à mettre à jour' });
  }

  const connection = await pool.getConnection();
  try {
    await connection.beginTransaction();
    const [[order]] = await connection.query('SELECT status FROM orders WHERE id = ? FOR UPDATE', [id]);
    if (!order) {
      await connection.rollback();
      connection.release();
      return res.status(404).json({ error: 'Commande non trouvée' });
    }

    // Annulation : remise en stock ; réactivation : stock de nouveau déduit
    const wasCancelled = order.status === 'cancelled';
    const willBeCancelled = status ? status === 'cancelled' : wasCancelled;
    if (wasCancelled !== willBeCancelled) {
      const [items] = await connection.query('SELECT product_id, quantity FROM order_items WHERE order_id = ?', [id]);
      for (const item of items) {
        await connection.query(
          willBeCancelled
            ? 'UPDATE products SET stock = stock + ? WHERE id = ?'
            : 'UPDATE products SET stock = GREATEST(0, stock - ?) WHERE id = ?',
          [item.quantity, item.product_id]
        );
      }
    }

    const fields = [];
    const values = [];
    if (status) { fields.push('status = ?'); values.push(status); }
    if (notes !== undefined) { fields.push('notes = ?'); values.push(String(notes).slice(0, 2000)); }
    values.push(id);
    await connection.query(`UPDATE orders SET ${fields.join(', ')} WHERE id = ?`, values);

    await connection.commit();
    connection.release();
    res.json({ id, status: status || order.status, notes });
  } catch (error) {
    await connection.rollback();
    connection.release();
    console.error('Update order status error:', error);
    res.status(500).json({ error: 'Erreur mise à jour commande' });
  }
};

app.put('/api/orders/:id/status', authenticateToken, requireAdmin, handleOrderUpdate);
app.put('/api/orders/:id', authenticateToken, requireAdmin, handleOrderUpdate);

// ==========================================
// 4. CERTIFICATE API
// ==========================================
app.get('/api/certificate/:orderId', async (req, res) => {
  try {
    const { orderId } = req.params;
    const [orders] = await pool.query('SELECT * FROM orders WHERE id = ?', [orderId]);

    if (orders.length === 0) {
      return res.status(404).json({ error: 'Certificat non trouvé pour cette commande' });
    }

    const order = orders[0];
    const [items] = await pool.query('SELECT * FROM order_items WHERE order_id = ?', [orderId]);

    const certData = {
      orderId: order.id,
      certificateSerial: order.certificate_serial || `CERT-2026-${order.id}`,
      issueDate: order.created_at,
      customerName: order.customer_name,
      customerPhone: order.customer_phone,
      customerAddress: `${order.customer_address || ''}, ${order.customer_city || ''} (${order.customer_governorate || ''})`,
      warrantyDuration: '3 ANS (Eco-Sac garanti À VIE)',
      standardConformity: 'Normes Européennes ISO 9001 / ACS Attestation de Conformité Sanitaire / Delrin-Hostaform',
      subtotal: parseFloat(order.subtotal) || 0,
      deliveryFee: parseFloat(order.delivery_fee) !== undefined ? parseFloat(order.delivery_fee) : 8.0,
      total: parseFloat(order.total) || 0,
      items: items.map(item => ({
        id: item.id,
        productId: item.product_id,
        name: item.name,
        price: parseFloat(item.price) || 0,
        quantity: item.quantity,
        serials: typeof item.serials === 'string' ? JSON.parse(item.serials) : (item.serials || []),
      })),
      issuer: {
        company: 'ECOPOWER TUNISIE / ECOGAM SARL',
        technicalManager: 'Pascal FABRE & Service Qualité',
        phone: '+216 98 000 000 / eceau-lo@orange.fr',
        officialStamp: 'CERTIFIÉ CONFORME AUX NORMES HYDRO-ÉCONOMIE'
      }
    };

    res.json(certData);
  } catch (error) {
    console.error('Get certificate error:', error);
    res.status(500).json({ error: 'Erreur lors de la génération du certificat' });
  }
});

// ==========================================
// 5. B2B LEADS API
// ==========================================
app.get('/api/leads', authenticateToken, requireAdmin, async (req, res) => {
  try {
    const [leads] = await pool.query('SELECT * FROM leads ORDER BY created_at DESC');
    const formatted = leads.map(l => ({
      id: l.id,
      date: l.created_at,
      company: l.company,
      contactPerson: l.contact_person,
      role: l.role,
      phone: l.phone,
      email: l.email || '',
      type: l.type,
      roomsCount: l.rooms_count,
      currentWaterBillMonthly: l.current_water_bill_monthly,
      interest: l.interest,
      status: l.status,
      notes: l.notes || '',
    }));
    res.json(formatted);
  } catch (error) {
    console.error('Get leads error:', error);
    res.status(500).json({ error: 'Erreur récupération des demandes B2B' });
  }
});

app.post('/api/leads', orderLimiter, async (req, res) => {
  try {
    const leadData = req.body || {};
    if (!String(leadData.company || '').trim() || String(leadData.phone || '').replace(/[^0-9]/g, '').length < 8) {
      return res.status(400).json({ error: "Indiquez le nom de l'établissement et un numéro de téléphone valide." });
    }
    const [[last]] = await pool.query("SELECT MAX(CAST(SUBSTRING(id, 6) AS UNSIGNED)) AS lastNum FROM leads WHERE id LIKE 'LEAD-%'");
    const leadId = `LEAD-${Math.max(200, last.lastNum || 0) + 1}`;

    await pool.query(
      `INSERT INTO leads (id, company, contact_person, role, phone, email, type, rooms_count, current_water_bill_monthly, interest, status, notes)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      [
        leadId,
        leadData.company || 'Établissement',
        leadData.contactPerson || '',
        leadData.role || '',
        leadData.phone || '',
        leadData.email || null,
        leadData.type || 'entreprise',
        parseInt(leadData.roomsCount, 10) || 0,
        leadData.currentWaterBillMonthly || '',
        leadData.interest || 'Diagnostic et audit gratuit',
        'new',
        leadData.notes || '',
      ]
    );

    const newLead = {
      id: leadId,
      date: new Date().toISOString(),
      company: leadData.company,
      contactPerson: leadData.contactPerson,
      role: leadData.role,
      phone: leadData.phone,
      email: leadData.email,
      type: leadData.type,
      roomsCount: leadData.roomsCount,
      currentWaterBillMonthly: leadData.currentWaterBillMonthly,
      interest: leadData.interest,
      status: 'new',
      notes: leadData.notes,
    };

    res.status(201).json(newLead);
  } catch (error) {
    console.error('Create lead error:', error);
    res.status(500).json({ error: 'Erreur enregistrement demande B2B' });
  }
});

app.put('/api/leads/:id', authenticateToken, requireAdmin, async (req, res) => {
  try {
    const { id } = req.params;
    const { status, notes } = req.body;

    const fields = [];
    const values = [];

    if (status) { fields.push('status = ?'); values.push(status); }
    if (notes !== undefined) { fields.push('notes = ?'); values.push(notes); }

    if (fields.length === 0) {
      return res.status(400).json({ error: 'Rien à mettre à jour' });
    }

    values.push(id);
    const [result] = await pool.query(`UPDATE leads SET ${fields.join(', ')} WHERE id = ?`, values);

    if (result.affectedRows === 0) {
      return res.status(404).json({ error: 'Demande non trouvée' });
    }

    const [rows] = await pool.query('SELECT * FROM leads WHERE id = ?', [id]);
    res.json(rows[0]);
  } catch (error) {
    console.error('Update lead error:', error);
    res.status(500).json({ error: 'Erreur mise à jour demande B2B' });
  }
});

// ==========================================
// 6. STATS API (Admin KPI)
// ==========================================
app.get('/api/stats', authenticateToken, requireAdmin, async (req, res) => {
  try {
    const valid = "status <> 'cancelled'";
    const [[rev]] = await pool.query(`SELECT COALESCE(SUM(total), 0) AS revenue, COUNT(*) AS orders, COALESCE(AVG(total), 0) AS avgBasket FROM orders WHERE ${valid}`);
    const [[all]] = await pool.query('SELECT COUNT(*) AS count FROM orders');
    const [[month]] = await pool.query(
      `SELECT COALESCE(SUM(total), 0) AS revenue, COUNT(*) AS orders FROM orders
       WHERE ${valid} AND created_at >= DATE_FORMAT(CURDATE(), '%Y-%m-01')`
    );
    const [[prevMonth]] = await pool.query(
      `SELECT COALESCE(SUM(total), 0) AS revenue, COUNT(*) AS orders FROM orders
       WHERE ${valid} AND created_at >= DATE_FORMAT(CURDATE() - INTERVAL 1 MONTH, '%Y-%m-01')
         AND created_at < DATE_FORMAT(CURDATE(), '%Y-%m-01')`
    );
    const [[toCollect]] = await pool.query(
      "SELECT COALESCE(SUM(total), 0) AS amount, COUNT(*) AS count FROM orders WHERE status IN ('pending', 'confirmed', 'shipped')"
    );
    const [byStatus] = await pool.query('SELECT status, COUNT(*) AS count, COALESCE(SUM(total), 0) AS total FROM orders GROUP BY status');
    const [daily] = await pool.query(
      `SELECT DATE_FORMAT(created_at, '%Y-%m-%d') AS day, COUNT(*) AS orders, COALESCE(SUM(total), 0) AS revenue
       FROM orders WHERE ${valid} AND created_at >= CURDATE() - INTERVAL 29 DAY
       GROUP BY day ORDER BY day`
    );
    const [topProducts] = await pool.query(
      `SELECT oi.product_id AS productId, MAX(oi.name) AS name, SUM(oi.quantity) AS quantity, SUM(oi.quantity * oi.price) AS revenue
       FROM order_items oi JOIN orders o ON o.id = oi.order_id
       WHERE o.${valid} GROUP BY oi.product_id ORDER BY revenue DESC LIMIT 5`
    );
    const [byGovernorate] = await pool.query(
      `SELECT customer_governorate AS governorate, COUNT(*) AS orders, COALESCE(SUM(total), 0) AS revenue
       FROM orders WHERE ${valid} GROUP BY customer_governorate ORDER BY revenue DESC LIMIT 6`
    );
    const [[leads]] = await pool.query("SELECT COUNT(*) AS total, SUM(status = 'new') AS fresh FROM leads");
    const [[lowStock]] = await pool.query('SELECT COUNT(*) AS count FROM products WHERE stock <= 10');

    // Série continue sur 30 jours (jours sans commande à 0)
    const series = [];
    for (let i = 29; i >= 0; i--) {
      const d = new Date();
      d.setDate(d.getDate() - i);
      const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
      const row = daily.find((r) => r.day === key);
      series.push({ day: key, orders: row ? Number(row.orders) : 0, revenue: row ? parseFloat(row.revenue) : 0 });
    }

    const num = (v) => parseFloat(v) || 0;
    res.json({
      revenue: num(rev.revenue),
      totalOrders: Number(all.count) || 0,
      validOrders: Number(rev.orders) || 0,
      avgBasket: num(rev.avgBasket),
      monthRevenue: num(month.revenue),
      monthOrders: Number(month.orders) || 0,
      prevMonthRevenue: num(prevMonth.revenue),
      prevMonthOrders: Number(prevMonth.orders) || 0,
      toCollect: num(toCollect.amount),
      toCollectCount: Number(toCollect.count) || 0,
      pendingOrders: Number(byStatus.find((r) => r.status === 'pending')?.count) || 0,
      byStatus: byStatus.map((r) => ({ status: r.status, count: Number(r.count), total: num(r.total) })),
      daily: series,
      topProducts: topProducts.map((r) => ({ ...r, quantity: Number(r.quantity), revenue: num(r.revenue) })),
      byGovernorate: byGovernorate.map((r) => ({ ...r, orders: Number(r.orders), revenue: num(r.revenue) })),
      totalLeads: Number(leads.total) || 0,
      newLeads: Number(leads.fresh) || 0,
      lowStockProducts: Number(lowStock.count) || 0,
    });
  } catch (error) {
    console.error('Stats error:', error);
    res.status(500).json({ error: 'Erreur calcul statistiques' });
  }
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

// Start Express with MySQL
async function startServer() {
  try {
    await initDb();
    app.listen(PORT, () => {
      console.log(`[ECOPOWER API] Server running on port ${PORT} with MySQL!`);
    });
  } catch (err) {
    console.error('[ECOPOWER API] Failed to start server:', err);
    process.exit(1);
  }
}

startServer();
