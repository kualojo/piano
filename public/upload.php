<?php
require __DIR__ . '/../src/bootstrap.php';

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    header('Location: ./');
    exit;
}
$f = $_FILES['pdf'] ?? null;
if (!$f || $f['error'] !== UPLOAD_ERR_OK) {
    fail(400, 'The upload did not arrive. Files can be up to ' . config('max_upload_mb') . ' MB.');
}
if ($f['size'] > config('max_upload_mb') * 1024 * 1024) {
    fail(400, 'That file is too big. Files can be up to ' . config('max_upload_mb') . ' MB.');
}
$head = (string) file_get_contents($f['tmp_name'], false, null, 0, 5);
if ($head !== '%PDF-') {
    fail(400, 'That file is not a PDF.');
}

$title = trim(preg_replace('/\.pdf$/i', '', basename($f['name'])) ?? '') ?: 'Your piece';
$job = Jobs::create(['title' => mb_substr($title, 0, 120), 'status' => 'new']);
move_uploaded_file($f['tmp_name'], $job->file('source.pdf'));

$check = Converter::check($job->file('source.pdf'));
if (empty($check['ok'])) {
    $job->meta['status'] = 'unsupported';
    $job->save();
    fail(422, $check['reason'] ?? 'We could not read this file.');
}
if (($check['pages'] ?? 0) > config('max_pages')) {
    fail(422, 'That piece has too many pages. The limit is ' . config('max_pages') . '.');
}
if (!Converter::convert($job)) {
    $job->meta['status'] = 'failed';
    $job->save();
    fail(500, 'We could not add letters to this piece. We have kept the file so we can look into it.');
}
$job->meta['status'] = 'done';
$job->meta['pages'] = $check['pages'];
$job->save();
header('Location: view.php?id=' . $job->id);
