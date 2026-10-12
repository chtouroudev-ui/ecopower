<?php

use Illuminate\Support\Facades\Route;

// Application React (SPA) : toutes les URL hors /api renvoient la même page.
Route::view('/{any?}', 'app')->where('any', '^(?!api(/|$)).*$');
