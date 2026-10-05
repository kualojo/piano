<?php
// Copy to config.php on the server (it is not in git) and fill in.
return [
    // Public address of the site, no trailing slash
    'base_url' => 'https://example.com',

    // Python with PyMuPDF installed; the deploy creates this virtualenv
    'python' => __DIR__ . '/.venv/bin/python',

    // Free preview: how many lines (systems) of music are shown and played
    'preview_lines' => 3,

    // Biggest upload accepted, in MB, and most pages
    'max_upload_mb' => 15,
    'max_pages' => 20,

    // Price per piece, in pence
    'price_pence' => 299,
    'currency' => 'gbp',

    // Stripe keys (Dashboard > Developers > API keys / Webhooks). Leave empty to run without payments.
    'stripe_secret_key' => '',
    'stripe_webhook_secret' => '',

    // Only for testing without Stripe: show an "unlock for free" button
    'demo_unlock' => false,

    // Converted files are deleted after this many days
    'keep_days' => 30,
];
