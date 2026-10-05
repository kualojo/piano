<?php
require __DIR__ . '/../src/bootstrap.php';

// Notes for the player. Until the piece is paid for, only the preview lines leave the server.
$job = job_from_request();
$data = json_decode((string) @file_get_contents($job->file('notes.json')), true) ?: ['notes' => []];
$data['paid'] = $job->paid();
if (!$job->paid()) {
    $limit = (int) config('preview_lines');
    $data['notes'] = array_values(array_filter($data['notes'], fn ($n) => $n['line'] < $limit));
    $data['preview_lines'] = $limit;
}
header('Content-Type: application/json');
header('Cache-Control: private, no-store');
echo json_encode($data);
