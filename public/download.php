<?php
require __DIR__ . '/../src/bootstrap.php';

$job = job_from_request();
if (!$job->paid()) {
    header('Location: view.php?id=' . $job->id);
    exit;
}
$name = preg_replace('/[^\w\- ]+/u', '', $job->title()) . ' - with note letters.pdf';
header('Content-Type: application/pdf');
header('Content-Disposition: ' . (isset($_GET['inline']) ? 'inline' : 'attachment') . '; filename="' . $name . '"');
header('Cache-Control: private');
readfile($job->file('letters.pdf'));
