<?php
require __DIR__ . '/../src/bootstrap.php';

$job = job_from_request();
if ($job->paid()) {
    header('Location: view.php?id=' . $job->id);
    exit;
}
if (Stripe::enabled()) {
    header('Location: ' . Stripe::checkoutUrl($job), true, 303);
    exit;
}
if (config('demo_unlock')) {
    $job->markPaid('demo');
    header('Location: view.php?id=' . $job->id);
    exit;
}
fail(503, 'Payments are not switched on yet.');
