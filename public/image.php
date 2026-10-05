<?php
require __DIR__ . '/../src/bootstrap.php';

$job = job_from_request();
$n = max(1, (int) ($_GET['n'] ?? 1));
$file = $job->file("preview/page-$n.png");
if (!is_file($file)) {
    fail(404, 'No such page.');
}
header('Content-Type: image/png');
header('Cache-Control: private, max-age=86400');
readfile($file);
