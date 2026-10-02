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

app.use(cors());
app.use(express.json());

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

// Optional Auth (doesn't reject if not authenticated)
function optionalAuth(req, res, next) {
  const authHeader = req.headers['authorization'];
  const token = authHeader && authHeader.split(' ')[1];
  if (!token) return next();

  jwt.verify(token, JWT_SECRET, (err, decoded) => {
    if (!err) {
      req.user = decoded;
    }
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

// Register
app.post('/api/auth/register', async (req, res) => {
  try {
    const { name, email, password, phone } = req.body;
    if (!name || !email || !password) {
      return res.status(400).json({ error: 'Veuillez renseigner le nom, email et mot de passe.' });
    }

    const [existing] = await pool.query('SELECT id FROM users WHERE email = ?', [email.trim().toLowerCase()]);
    if (existing.length > 0) {
      return res.status(409).json({ error: 'Un compte existe déjà avec cette adresse email.' });
    }

    const hashedPassword = await bcrypt.hash(password, 10);
    const [result] = await pool.query(
      'INSERT INTO users (name, email, password, role, phone) VALUES (?, ?, ?, ?, ?)',
      [name.trim(), email.trim().toLowerCase(), hashedPassword, 'client', phone || null]
    );

    const user = {
      id: result.insertId,
      name: name.trim(),
      email: email.trim().toLowerCase(),
      role: 'client',
      phone: phone || null,
    };

    const token = jwt.sign(user, JWT_SECRET, { expiresIn: '7d' });
    res.status(201).json({ message: 'Compte créé avec succès', token, user });
  } catch (error) {
    console.error('Register error:', error);
    res.status(500).json({ error: 'Erreur lors de la création du compte' });
  }
});

// Login
app.post('/api/auth/login', async (req, res) => {
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
    if (!match) {
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

// Update product
app.put('/api/products/:id', async (req, res) => {
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

// Get all orders (with items)
app.get('/api/orders', async (req, res) => {
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

// Get user orders (authenticated)
app.get('/api/user/orders', authenticateToken, async (req, res) => {
  try {
    const userEmail = req.user.email;
    const userId = req.user.id;

    const [orders] = await pool.query(
      'SELECT * FROM orders WHERE user_id = ? OR customer_email = ? ORDER BY created_at DESC',
      [userId, userEmail]
    );

    const [items] = await pool.query(
      'SELECT * FROM order_items WHERE order_id IN (?)',
      [orders.length > 0 ? orders.map(o => o.id) : ['none']]
    );

    const formattedOrders = orders.map(o => ({
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
      items: items.filter(i => i.order_id === o.id).map(i => ({
        id: i.id,
        productId: i.product_id,
        name: i.name,
        price: parseFloat(i.price),
        quantity: i.quantity,
        serials: typeof i.serials === 'string' ? JSON.parse(i.serials) : (i.serials || []),
      })),
      subtotal: parseFloat(o.subtotal),
      deliveryFee: parseFloat(o.delivery_fee),
      total: parseFloat(o.total),
      paymentMethod: o.payment_method,
      status: o.status,
      certificateSerial: o.certificate_serial,
      notes: o.notes,
    }));

    res.json(formattedOrders);
  } catch (error) {
    console.error('User orders error:', error);
    res.status(500).json({ error: 'Erreur récupération commandes utilisateur' });
  }
});

// Public Track Order (by Order ID or Phone number)
app.get('/api/orders/track/:query', async (req, res) => {
  try {
    const { query } = req.params;
    const cleanQuery = query.trim();

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

// Create Order (public checkout)
app.post('/api/orders', optionalAuth, async (req, res) => {
  const connection = await pool.getConnection();
  try {
    const { customer, items, paymentMethod = 'cod', notes = '' } = req.body;
    if (!customer || !items || !items.length) {
      connection.release();
      return res.status(400).json({ error: 'Données de commande incomplètes' });
    }

    await connection.beginTransaction();

    // 1. Get current count to generate next ID
    const [countRows] = await connection.query('SELECT COUNT(*) as count FROM orders');
    const orderIndex = countRows[0].count + 1;
    const newOrderId = `ECO-${1000 + orderIndex}`;
    const certSerial = `CERT-${new Date().getFullYear()}-${newOrderId}`;

    let subtotal = 0;
    const enrichedItems = [];

    // 2. Process items, verify prices, decrement stock, generate serials
    for (const item of items) {
      const [prodRows] = await connection.query('SELECT * FROM products WHERE id = ?', [item.productId]);
      const prod = prodRows[0];

      const price = prod ? parseFloat(prod.price) : parseFloat(item.price || 0);
      const qty = parseInt(item.quantity, 10) || 1;
      subtotal += price * qty;

      const serials = [];
      for (let i = 0; i < qty; i++) {
        serials.push(generateSerial(item.productId, i));
      }

      enrichedItems.push({
        productId: item.productId,
        name: prod ? prod.name : (item.name || 'Produit'),
        price: price,
        quantity: qty,
        serials: serials,
      });

      // Deduct stock in DB
      if (prod) {
        await connection.query(
          'UPDATE products SET stock = GREATEST(0, stock - ?) WHERE id = ?',
          [qty, item.productId]
        );
      }
    }

    const deliveryFee = subtotal >= 120 ? 0 : 8.0;
    const total = subtotal + deliveryFee;
    const userId = req.user ? req.user.id : null;

    // 3. Insert order
    await connection.query(
      `INSERT INTO orders 
       (id, user_id, customer_name, customer_phone, customer_email, customer_address, customer_city, customer_governorate, subtotal, delivery_fee, total, payment_method, status, certificate_serial, notes)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      [
        newOrderId,
        userId,
        customer.fullName || 'Client',
        customer.phone || '',
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
        notes || 'Commande passée en ligne',
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
    console.error('Create order error:', error);
    res.status(500).json({ error: 'Erreur lors de la validation de la commande' });
  }
});

// Update order status
app.put('/api/orders/:id/status', async (req, res) => {
  try {
    const { id } = req.params;
    const { status, notes } = req.body;

    const fields = [];
    const values = [];

    if (status) { fields.push('status = ?'); values.push(status); }
    if (notes !== undefined) { fields.push('notes = ?'); values.push(notes); }

    if (fields.length === 0) {
      return res.status(400).json({ error: 'Aucune donnée à mettre à jour' });
    }

    values.push(id);
    const [result] = await pool.query(`UPDATE orders SET ${fields.join(', ')} WHERE id = ?`, values);

    if (result.affectedRows === 0) {
      return res.status(404).json({ error: 'Commande non trouvée' });
    }

    const [rows] = await pool.query('SELECT * FROM orders WHERE id = ?', [id]);
    res.json(rows[0]);
  } catch (error) {
    console.error('Update order status error:', error);
    res.status(500).json({ error: 'Erreur mise à jour commande' });
  }
});

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
      testedPressure: 'Tenue jusqu’à 25 Bars - Résistant aux chocs thermiques & chlorés',
      items: items.map(item => ({
        name: item.name,
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
app.get('/api/leads', async (req, res) => {
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

app.post('/api/leads', async (req, res) => {
  try {
    const leadData = req.body;
    const [countRows] = await pool.query('SELECT COUNT(*) as count FROM leads');
    const leadId = `LEAD-${200 + countRows[0].count + 1}`;

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

app.put('/api/leads/:id', async (req, res) => {
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
app.get('/api/stats', async (req, res) => {
  try {
    const [rev] = await pool.query('SELECT COALESCE(SUM(total), 0) as totalRevenue, COUNT(*) as totalOrders FROM orders');
    const [pendingOrders] = await pool.query('SELECT COUNT(*) as count FROM orders WHERE status = "pending"');
    const [leads] = await pool.query('SELECT COUNT(*) as count FROM leads');
    const [newLeads] = await pool.query('SELECT COUNT(*) as count FROM leads WHERE status = "new"');
    const [lowStock] = await pool.query('SELECT COUNT(*) as count FROM products WHERE stock <= 10');

    res.json({
      revenue: parseFloat(rev[0].totalRevenue) || 0,
      totalOrders: rev[0].totalOrders || 0,
      pendingOrders: pendingOrders[0].count || 0,
      totalLeads: leads[0].count || 0,
      newLeads: newLeads[0].count || 0,
      lowStockProducts: lowStock[0].count || 0,
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
