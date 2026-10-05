<?php
require __DIR__ . '/../src/bootstrap.php';

$title = 'Sheet music with the letter names written in';
ob_start(); ?>
<section class="hero">
  <h1>Can't read music? Play it anyway.</h1>
  <p>Upload a piano PDF and we write the letter name above or below every note: right hand in red, left hand in blue.
     Then hear it, and follow it on a piano roll.</p>
  <form class="upload" action="upload.php" method="post" enctype="multipart/form-data">
    <label class="drop">
      <input type="file" name="pdf" accept="application/pdf" required>
      <span>Choose a PDF of sheet music</span>
    </label>
    <button type="submit">Add the letters</button>
    <p class="small">Free preview of the first <?= (int) config('preview_lines') ?> lines, no sign-up.
       The whole piece, the PDF and playback are <?= e(price_label()) ?>.</p>
  </form>
  <p class="small">Works with PDFs exported from music software (Sibelius for now). Scans and photos are coming later.</p>
</section>
<?php $body = ob_get_clean();
require APP_ROOT . '/src/views/layout.php';
