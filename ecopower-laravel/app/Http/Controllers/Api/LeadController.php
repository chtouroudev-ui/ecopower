<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use App\Support\Format;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;
use Throwable;

/** Demandes B2B (hôtels, cliniques, universités...). */
class LeadController extends Controller
{
    public function index()
    {
        return response()->json(DB::table('leads')->orderByDesc('created_at')->get()->map(fn ($l) => [
            'id' => $l->id,
            'date' => Format::date($l->created_at),
            'company' => $l->company,
            'contactPerson' => $l->contact_person,
            'role' => $l->role,
            'phone' => $l->phone,
            'email' => $l->email ?: '',
            'type' => $l->type,
            'roomsCount' => (int) $l->rooms_count,
            'currentWaterBillMonthly' => $l->current_water_bill_monthly,
            'interest' => $l->interest,
            'status' => $l->status,
            'notes' => $l->notes ?: '',
        ])->values());
    }

    public function store(Request $request)
    {
        $d = $request->all();
        if (trim((string) ($d['company'] ?? '')) === '' || strlen(preg_replace('/[^0-9]/', '', (string) ($d['phone'] ?? ''))) < 8) {
            return response()->json(['error' => "Indiquez le nom de l'établissement et un numéro de téléphone valide."], 400);
        }

        try {
            $last = DB::selectOne("SELECT MAX(CAST(SUBSTRING(id, 6) AS UNSIGNED)) AS lastNum FROM leads WHERE id LIKE 'LEAD-%'");
            $leadId = 'LEAD-'.(max(200, (int) ($last->lastNum ?? 0)) + 1);

            DB::table('leads')->insert([
                'id' => $leadId,
                'company' => ($d['company'] ?? null) ?: 'Établissement',
                'contact_person' => ($d['contactPerson'] ?? null) ?: '',
                'role' => ($d['role'] ?? null) ?: '',
                'phone' => ($d['phone'] ?? null) ?: '',
                'email' => ($d['email'] ?? null) ?: null,
                'type' => ($d['type'] ?? null) ?: 'entreprise',
                'rooms_count' => (int) ($d['roomsCount'] ?? 0),
                'current_water_bill_monthly' => (string) (($d['currentWaterBillMonthly'] ?? null) ?: ''),
                'interest' => ($d['interest'] ?? null) ?: 'Diagnostic et audit gratuit',
                'status' => 'new',
                'notes' => ($d['notes'] ?? null) ?: '',
            ]);
        } catch (Throwable $e) {
            report($e);

            return response()->json(['error' => 'Erreur enregistrement demande B2B'], 500);
        }

        return response()->json([
            'id' => $leadId,
            'date' => now()->utc()->format('Y-m-d\TH:i:s.v\Z'),
            'company' => $d['company'] ?? null,
            'contactPerson' => $d['contactPerson'] ?? null,
            'role' => $d['role'] ?? null,
            'phone' => $d['phone'] ?? null,
            'email' => $d['email'] ?? null,
            'type' => $d['type'] ?? null,
            'roomsCount' => $d['roomsCount'] ?? null,
            'currentWaterBillMonthly' => $d['currentWaterBillMonthly'] ?? null,
            'interest' => $d['interest'] ?? null,
            'status' => 'new',
            'notes' => $d['notes'] ?? null,
        ], 201);
    }

    public function update(Request $request, string $id)
    {
        $fields = [];
        if ($request->input('status')) {
            $fields['status'] = $request->input('status');
        }
        if ($request->exists('notes')) {
            $fields['notes'] = $request->input('notes');
        }
        if (! $fields) {
            return response()->json(['error' => 'Rien à mettre à jour'], 400);
        }

        if (! DB::table('leads')->where('id', $id)->exists()) {
            return response()->json(['error' => 'Demande non trouvée'], 404);
        }
        DB::table('leads')->where('id', $id)->update($fields);

        return response()->json(Format::row(DB::table('leads')->where('id', $id)->first()));
    }
}
