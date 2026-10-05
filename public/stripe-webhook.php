<?php
require __DIR__ . '/../src/bootstrap.php';

// Stripe Dashboard > Developers > Webhooks: point checkout.session.completed at this URL.
$event = Stripe::webhookEvent((string) file_get_contents('php://input'), $_SERVER['HTTP_STRIPE_SIGNATURE'] ?? '');
if (!$event) {
    http_response_code(400);
    exit;
}
if ($event['type'] === 'checkout.session.completed') {
    $s = $event['data']['object'];
    $job = Jobs::find((string) ($s['client_reference_id'] ?? ''));
    if ($job && ($s['payment_status'] ?? '') === 'paid' && !$job->paid()) {
        $job->markPaid($s['id']);
    }
}
http_response_code(200);
