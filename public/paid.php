<?php
require __DIR__ . '/../src/bootstrap.php';

// Stripe sends the buyer back here. The webhook also marks the piece paid, in case they close the tab.
$job = job_from_request();
$session = (string) ($_GET['session'] ?? '');
if (!$job->paid() && Stripe::enabled() && Stripe::sessionPaidFor($session, $job)) {
    $job->markPaid($session);
}
header('Location: view.php?id=' . $job->id);
