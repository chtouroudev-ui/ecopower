<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use Illuminate\Support\Facades\DB;

/** Indicateurs du tableau de bord admin. */
class StatsController extends Controller
{
    public function __invoke()
    {
        $valid = "status <> 'cancelled'";

        $rev = DB::selectOne("SELECT COALESCE(SUM(total), 0) AS revenue, COUNT(*) AS orders, COALESCE(AVG(total), 0) AS avgBasket FROM orders WHERE $valid");
        $all = DB::selectOne('SELECT COUNT(*) AS count FROM orders');
        $month = DB::selectOne(
            "SELECT COALESCE(SUM(total), 0) AS revenue, COUNT(*) AS orders FROM orders
             WHERE $valid AND created_at >= DATE_FORMAT(CURDATE(), '%Y-%m-01')"
        );
        $prevMonth = DB::selectOne(
            "SELECT COALESCE(SUM(total), 0) AS revenue, COUNT(*) AS orders FROM orders
             WHERE $valid AND created_at >= DATE_FORMAT(CURDATE() - INTERVAL 1 MONTH, '%Y-%m-01')
               AND created_at < DATE_FORMAT(CURDATE(), '%Y-%m-01')"
        );
        $toCollect = DB::selectOne(
            "SELECT COALESCE(SUM(total), 0) AS amount, COUNT(*) AS count FROM orders WHERE status IN ('pending', 'confirmed', 'shipped') AND payment_status <> 'paid'"
        );
        $byStatus = DB::select('SELECT status, COUNT(*) AS count, COALESCE(SUM(total), 0) AS total FROM orders GROUP BY status');
        $daily = collect(DB::select(
            "SELECT DATE_FORMAT(created_at, '%Y-%m-%d') AS day, COUNT(*) AS orders, COALESCE(SUM(total), 0) AS revenue
             FROM orders WHERE $valid AND created_at >= CURDATE() - INTERVAL 29 DAY
             GROUP BY day ORDER BY day"
        ))->keyBy('day');
        $topProducts = DB::select(
            "SELECT oi.product_id AS productId, MAX(oi.name) AS name, SUM(oi.quantity) AS quantity, SUM(oi.quantity * oi.price) AS revenue
             FROM order_items oi JOIN orders o ON o.id = oi.order_id
             WHERE o.$valid GROUP BY oi.product_id ORDER BY revenue DESC LIMIT 5"
        );
        $byGovernorate = DB::select(
            "SELECT customer_governorate AS governorate, COUNT(*) AS orders, COALESCE(SUM(total), 0) AS revenue
             FROM orders WHERE $valid GROUP BY customer_governorate ORDER BY revenue DESC LIMIT 6"
        );
        $leads = DB::selectOne("SELECT COUNT(*) AS total, SUM(status = 'new') AS fresh FROM leads");
        $lowStock = DB::selectOne('SELECT COUNT(*) AS count FROM products WHERE stock <= 10');

        // Série continue sur 30 jours (jours sans commande à 0)
        $series = [];
        for ($i = 29; $i >= 0; $i--) {
            $key = now()->subDays($i)->format('Y-m-d');
            $row = $daily[$key] ?? null;
            $series[] = ['day' => $key, 'orders' => $row ? (int) $row->orders : 0, 'revenue' => $row ? (float) $row->revenue : 0];
        }

        $pending = collect($byStatus)->firstWhere('status', 'pending');

        return response()->json([
            'revenue' => (float) $rev->revenue,
            'totalOrders' => (int) $all->count,
            'validOrders' => (int) $rev->orders,
            'avgBasket' => (float) $rev->avgBasket,
            'monthRevenue' => (float) $month->revenue,
            'monthOrders' => (int) $month->orders,
            'prevMonthRevenue' => (float) $prevMonth->revenue,
            'prevMonthOrders' => (int) $prevMonth->orders,
            'toCollect' => (float) $toCollect->amount,
            'toCollectCount' => (int) $toCollect->count,
            'pendingOrders' => $pending ? (int) $pending->count : 0,
            'byStatus' => array_map(fn ($r) => ['status' => $r->status, 'count' => (int) $r->count, 'total' => (float) $r->total], $byStatus),
            'daily' => $series,
            'topProducts' => array_map(fn ($r) => ['productId' => $r->productId, 'name' => $r->name, 'quantity' => (int) $r->quantity, 'revenue' => (float) $r->revenue], $topProducts),
            'byGovernorate' => array_map(fn ($r) => ['governorate' => $r->governorate, 'orders' => (int) $r->orders, 'revenue' => (float) $r->revenue], $byGovernorate),
            'totalLeads' => (int) $leads->total,
            'newLeads' => (int) $leads->fresh,
            'lowStockProducts' => (int) $lowStock->count,
        ]);
    }
}
