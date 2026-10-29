import mysql from 'mysql2/promise';
import bcrypt from 'bcryptjs';
import 'dotenv/config';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const DB_CONFIG = {
  host: process.env.DB_HOST || 'localhost',
  port: parseInt(process.env.DB_PORT || '3306', 10),
  user: process.env.DB_USER || 'root',
  password: process.env.DB_PASSWORD || '',
  waitForConnections: true,
  connectionLimit: 10,
  queueLimit: 0,
};

const DB_NAME = process.env.DB_NAME || 'ecopower_db';

export let pool = null;

export async function initDb() {
  try {
    // 1. Connect without database to ensure DB exists
    const initialConn = await mysql.createConnection(DB_CONFIG);
    await initialConn.query(`CREATE DATABASE IF NOT EXISTS \`${DB_NAME}\` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;`);
    await initialConn.end();
    console.log(`[ECOPOWER DB] Database "${DB_NAME}" confirmed/created.`);

    // 2. Initialize connection pool with the database
    pool = mysql.createPool({
      ...DB_CONFIG,
      database: DB_NAME,
    });

    // 3. Create tables
    await pool.query(`
      CREATE TABLE IF NOT EXISTS users (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(150) NOT NULL,
        email VARCHAR(191) NOT NULL UNIQUE,
        password VARCHAR(255) NOT NULL,
        role ENUM('admin', 'client') NOT NULL DEFAULT 'client',
        phone VARCHAR(50) DEFAULT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
      ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
    `);

    await pool.query(`
      CREATE TABLE IF NOT EXISTS products (
        id VARCHAR(100) PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        name_ar VARCHAR(255) DEFAULT NULL,
        category VARCHAR(100) DEFAULT 'packs',
        price DECIMAL(10, 2) NOT NULL,
        old_price DECIMAL(10, 2) DEFAULT NULL,
        rating DECIMAL(3, 1) DEFAULT 5.0,
        reviews_count INT DEFAULT 0,
        warranty VARCHAR(100) DEFAULT '3 ans',
        debit VARCHAR(50) DEFAULT NULL,
        image VARCHAR(255) DEFAULT NULL,
        description TEXT,
        features JSON DEFAULT NULL,
        stock INT DEFAULT 100,
        is_featured BOOLEAN DEFAULT FALSE,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
      ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
    `);

    await pool.query(`
      CREATE TABLE IF NOT EXISTS orders (
        id VARCHAR(100) PRIMARY KEY,
        user_id INT DEFAULT NULL,
        customer_name VARCHAR(150) NOT NULL,
        customer_phone VARCHAR(50) NOT NULL,
        customer_email VARCHAR(191) DEFAULT NULL,
        customer_address TEXT,
        customer_city VARCHAR(100) DEFAULT NULL,
        customer_governorate VARCHAR(100) DEFAULT NULL,
        subtotal DECIMAL(10, 2) NOT NULL,
        delivery_fee DECIMAL(10, 2) NOT NULL DEFAULT 8.00,
        total DECIMAL(10, 2) NOT NULL,
        payment_method VARCHAR(50) DEFAULT 'cod',
        status VARCHAR(50) DEFAULT 'pending',
        certificate_serial VARCHAR(100) DEFAULT NULL,
        notes TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_customer_phone (customer_phone),
        INDEX idx_customer_email (customer_email)
      ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
    `);

    await pool.query(`
      CREATE TABLE IF NOT EXISTS order_items (
        id INT AUTO_INCREMENT PRIMARY KEY,
        order_id VARCHAR(100) NOT NULL,
        product_id VARCHAR(100) NOT NULL,
        name VARCHAR(255) NOT NULL,
        price DECIMAL(10, 2) NOT NULL,
        quantity INT NOT NULL DEFAULT 1,
        serials JSON DEFAULT NULL,
        INDEX idx_order_id (order_id),
        CONSTRAINT fk_order FOREIGN KEY (order_id) REFERENCES orders (id) ON DELETE CASCADE
      ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
    `);

    await pool.query(`
      CREATE TABLE IF NOT EXISTS leads (
        id VARCHAR(100) PRIMARY KEY,
        date DATETIME DEFAULT CURRENT_TIMESTAMP,
        company VARCHAR(255) NOT NULL,
        contact_person VARCHAR(150) NOT NULL,
        role VARCHAR(100) DEFAULT NULL,
        phone VARCHAR(50) NOT NULL,
        email VARCHAR(191) DEFAULT NULL,
        type VARCHAR(50) DEFAULT 'entreprise',
        rooms_count INT DEFAULT 0,
        current_water_bill_monthly VARCHAR(100) DEFAULT NULL,
        interest VARCHAR(255) DEFAULT NULL,
        status VARCHAR(50) DEFAULT 'new',
        notes TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
      ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
    `);

    console.log('[ECOPOWER DB] All MySQL tables verified/created successfully.');

    // 4. Seed users if empty
    const [userRows] = await pool.query('SELECT COUNT(*) as count FROM users');
    if (userRows[0].count === 0) {
      const adminEmail = process.env.ADMIN_EMAIL || 'admin@ecopower.tn';
      const adminPassword = process.env.ADMIN_PASSWORD || 'admin123';
      const adminPass = await bcrypt.hash(adminPassword, 10);
      const clientPass = await bcrypt.hash(process.env.CLIENT_DEFAULT_PASSWORD || 'client123', 10);

      await pool.query(
        'INSERT INTO users (name, email, password, role, phone) VALUES (?, ?, ?, ?, ?)',
        ['Direction EcoPower', adminEmail, adminPass, 'admin', '+216 98 000 000']
      );

      await pool.query(
        'INSERT INTO users (name, email, password, role, phone) VALUES (?, ?, ?, ?, ?)',
        ['Client Particulier', 'client@ecopower.tn', clientPass, 'client', '+216 22 334 455']
      );
      console.log(`[ECOPOWER DB] Seeded admin (${adminEmail}) and client user.`);
    }

    // 5. Seed products from products.json if empty
    const [productRows] = await pool.query('SELECT COUNT(*) as count FROM products');
    if (productRows[0].count === 0) {
      const productsFile = path.join(__dirname, 'data', 'products.json');
      if (fs.existsSync(productsFile)) {
        console.log('[ECOPOWER DB] Seeding products from products.json...');
        const products = JSON.parse(fs.readFileSync(productsFile, 'utf-8'));
        for (const p of products) {
          await pool.query(
            `INSERT INTO products 
             (id, name, name_ar, category, price, old_price, rating, reviews_count, warranty, debit, image, description, features, stock, is_featured)
             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
            [
              p.id,
              p.name,
              p.nameAr || null,
              p.category || 'packs',
              p.price || 0,
              p.oldPrice || null,
              p.rating || 5,
              p.reviewsCount || 0,
              p.warranty || '3 ans',
              p.debit || null,
              p.image || null,
              p.description || '',
              JSON.stringify(p.features || []),
              p.stock !== undefined ? p.stock : 100,
              p.isFeatured ? 1 : 0,
            ]
          );
        }
        console.log(`[ECOPOWER DB] Seeded ${products.length} products.`);
      }
    }

    // 6. Seed orders from orders.json if empty
    const [orderRows] = await pool.query('SELECT COUNT(*) as count FROM orders');
    if (orderRows[0].count === 0) {
      const ordersFile = path.join(__dirname, 'data', 'orders.json');
      if (fs.existsSync(ordersFile)) {
        console.log('[ECOPOWER DB] Seeding orders from orders.json...');
        const orders = JSON.parse(fs.readFileSync(ordersFile, 'utf-8'));
        for (const o of orders) {
          const orderDate = o.date ? new Date(o.date) : new Date();
          await pool.query(
            `INSERT INTO orders 
             (id, customer_name, customer_phone, customer_email, customer_address, customer_city, customer_governorate, subtotal, delivery_fee, total, payment_method, status, certificate_serial, notes, created_at)
             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
            [
              o.id,
              o.customer?.fullName || 'Client',
              o.customer?.phone || '',
              o.customer?.email || null,
              o.customer?.address || '',
              o.customer?.city || '',
              o.customer?.governorate || 'Tunis',
              o.subtotal || 0,
              o.deliveryFee || 0,
              o.total || 0,
              o.paymentMethod || 'cod',
              o.status || 'pending',
              o.certificateSerial || `CERT-2026-${o.id}`,
              o.notes || '',
              orderDate,
            ]
          );

          if (o.items && Array.isArray(o.items)) {
            for (const item of o.items) {
              await pool.query(
                `INSERT INTO order_items (order_id, product_id, name, price, quantity, serials)
                 VALUES (?, ?, ?, ?, ?, ?)`,
                [
                  o.id,
                  item.productId || 'item',
                  item.name || 'Produit',
                  item.price || 0,
                  item.quantity || 1,
                  JSON.stringify(item.serials || []),
                ]
              );
            }
          }
        }
        console.log(`[ECOPOWER DB] Seeded ${orders.length} orders.`);
      }
    }

    // 7. Seed leads from leads.json if empty
    const [leadRows] = await pool.query('SELECT COUNT(*) as count FROM leads');
    if (leadRows[0].count === 0) {
      const leadsFile = path.join(__dirname, 'data', 'leads.json');
      if (fs.existsSync(leadsFile)) {
        console.log('[ECOPOWER DB] Seeding leads from leads.json...');
        const leads = JSON.parse(fs.readFileSync(leadsFile, 'utf-8'));
        for (const l of leads) {
          const leadDate = l.date ? new Date(l.date) : new Date();
          await pool.query(
            `INSERT INTO leads 
             (id, date, company, contact_person, role, phone, email, type, rooms_count, current_water_bill_monthly, interest, status, notes, created_at)
             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
            [
              l.id,
              leadDate,
              l.company || '',
              l.contactPerson || '',
              l.role || '',
              l.phone || '',
              l.email || null,
              l.type || 'entreprise',
              l.roomsCount || 0,
              l.currentWaterBillMonthly || '',
              l.interest || '',
              l.status || 'new',
              l.notes || '',
              leadDate,
            ]
          );
        }
        console.log(`[ECOPOWER DB] Seeded ${leads.length} leads.`);
      }
    }

    console.log('[ECOPOWER DB] MySQL Database fully ready and synchronized.');
    return pool;
  } catch (error) {
    console.error('[ECOPOWER DB] Database initialization error:', error);
    throw error;
  }
}
