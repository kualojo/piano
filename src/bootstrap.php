<?php
declare(strict_types=1);

const APP_ROOT = __DIR__ . '/..';

$configFile = file_exists(APP_ROOT . '/config.php') ? APP_ROOT . '/config.php' : APP_ROOT . '/config.example.php';
$GLOBALS['config'] = require $configFile;

require __DIR__ . '/Jobs.php';
require __DIR__ . '/Converter.php';
require __DIR__ . '/Stripe.php';

function config(string $key, mixed $default = null): mixed
{
    return $GLOBALS['config'][$key] ?? $default;
}

function e(?string $s): string
{
    return htmlspecialchars((string) $s, ENT_QUOTES, 'UTF-8');
}

function fail(int $code, string $message): never
{
    http_response_code($code);
    $title = 'Something went wrong';
    $body = '<p>' . e($message) . '</p><p><a href="./">Back to the start</a></p>';
    require APP_ROOT . '/src/views/layout.php';
    exit;
}

function job_from_request(): Job
{
    $job = Jobs::find((string) ($_GET['id'] ?? ''));
    if (!$job) {
        fail(404, 'We could not find that piece. Links last ' . config('keep_days') . ' days.');
    }
    return $job;
}

function price_label(): string
{
    $symbols = ['gbp' => '£', 'usd' => '$', 'eur' => '€'];
    return ($symbols[config('currency')] ?? '') . number_format(config('price_pence') / 100, 2);
}
