<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title><?= e($title ?? 'Letter Notes') ?> · Letter Notes</title>
<link rel="stylesheet" href="assets/style.css">
</head>
<body>
<header class="top"><a class="brand" href="./">Letter<span>Notes</span></a></header>
<main>
<?= $body ?>
</main>
<footer class="foot">Upload only music you have the right to use. Files are deleted after <?= (int) config('keep_days') ?> days.</footer>
</body>
</html>
