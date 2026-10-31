<?php

namespace App\Support;

use RuntimeException;

/** Erreur dont le message peut être renvoyé tel quel au client. */
class PublicError extends RuntimeException
{
}
