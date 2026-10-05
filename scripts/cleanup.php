<?php
// Daily cron: php ~/piano/scripts/cleanup.php
require __DIR__ . '/../src/bootstrap.php';
echo Jobs::cleanup((int) config('keep_days')) . " old pieces removed\n";
