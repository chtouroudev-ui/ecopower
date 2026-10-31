<?php

namespace Tests\Feature;

use Tests\TestCase;

class ExampleTest extends TestCase
{
    public function test_la_page_d_accueil_renvoie_la_spa(): void
    {
        $this->get('/')->assertOk()->assertSee('<div id="root"></div>', false);
    }

    public function test_les_routes_admin_exigent_un_jeton(): void
    {
        $this->getJson('/api/orders')->assertStatus(401)->assertJson(['error' => 'Accès non autorisé: token requis']);
    }
}
