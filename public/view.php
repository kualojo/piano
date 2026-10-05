<?php
require __DIR__ . '/../src/bootstrap.php';

$job = job_from_request();
$paid = $job->paid();
$images = glob($job->file('preview') . '/page-*.png') ?: [];
$title = $job->title();
ob_start(); ?>
<section class="piece">
  <h1><?= e($job->title()) ?></h1>
  <?php if ($paid): ?>
    <p class="actions"><a class="button" href="download.php?id=<?= e($job->id) ?>">Download the PDF</a>
      <span class="small">Keep this page's link to come back to it.</span></p>
  <?php else: ?>
    <div class="unlock">
      <p>This is a free preview of the first <?= (int) config('preview_lines') ?> lines.
         Unlock the whole piece to download the PDF and play it all.</p>
      <a class="button" href="checkout.php?id=<?= e($job->id) ?>">Unlock for <?= e(price_label()) ?></a>
    </div>
  <?php endif; ?>

  <div id="player" class="player" data-notes="notes.php?id=<?= e($job->id) ?>" data-paid="<?= $paid ? 1 : 0 ?>"
       data-unlock="checkout.php?id=<?= e($job->id) ?>">
    <div class="controls">
      <button type="button" data-act="play">▶ Play</button>
      <button type="button" data-act="restart">⟲ Start again</button>
      <label>Speed <input type="range" min="40" max="130" value="80" data-act="speed"> <output>80%</output></label>
      <label><input type="checkbox" data-hand="R" checked> <span class="rh">Right hand</span></label>
      <label><input type="checkbox" data-hand="L" checked> <span class="lh">Left hand</span></label>
    </div>
    <canvas></canvas>
    <p class="status small">Loading the piano…</p>
  </div>

  <?php if ($paid): ?>
    <iframe class="pdf" src="download.php?id=<?= e($job->id) ?>&inline=1" title="Sheet music"></iframe>
  <?php else: ?>
    <?php foreach ($images as $i => $img): ?>
      <img class="sheet" src="image.php?id=<?= e($job->id) ?>&n=<?= $i + 1 ?>" alt="Preview of the sheet music with letters">
    <?php endforeach; ?>
  <?php endif; ?>
</section>
<script src="assets/vendor/tone-14.8.49.min.js"></script>
<script src="assets/player.js"></script>
<?php $body = ob_get_clean();
require APP_ROOT . '/src/views/layout.php';
