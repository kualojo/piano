<?php
declare(strict_types=1);

/** Runs the Python converter in converter/ on an uploaded piece. */
final class Converter
{
    private const STYLE = ['--stack', '--fs=8', '--offset=0.8'];

    /** @return array{ok: bool, reason?: string, pages?: int} */
    public static function check(string $pdf): array
    {
        [$code, $out] = self::run([self::script('checkpdf.py'), $pdf], 30);
        $info = json_decode($out, true);
        if ($code !== 0 || !is_array($info)) {
            return ['ok' => false, 'reason' => 'We could not read this file.'];
        }
        return $info;
    }

    /** Makes letters.pdf + notes.json (full) and preview.pdf + preview/page-1.png (first lines). */
    public static function convert(Job $job): bool
    {
        $src = $job->file('source.pdf');
        [$full] = self::run(array_merge([self::script('letternotes.py'), $src, $job->file('letters.pdf')], self::STYLE,
            ['--json=' . $job->file('notes.json')]), 120);
        [$preview] = self::run(array_merge([self::script('letternotes.py'), $src, $job->file('preview.pdf')], self::STYLE,
            ['--preview=' . (int) config('preview_lines'), '--png=' . $job->file('preview')]), 60);
        return $full === 0 && $preview === 0 && is_file($job->file('notes.json'));
    }

    private static function script(string $name): string
    {
        return APP_ROOT . '/converter/' . $name;
    }

    /** @return array{0: int, 1: string} exit code and stdout */
    private static function run(array $args, int $timeout): array
    {
        $cmd = array_merge([config('python')], $args);
        $proc = proc_open($cmd, [1 => ['pipe', 'w'], 2 => ['pipe', 'w']], $pipes);
        if (!is_resource($proc)) {
            return [-1, ''];
        }
        stream_set_blocking($pipes[1], false);
        stream_set_blocking($pipes[2], false);
        $out = $err = '';
        $deadline = time() + $timeout;
        while (true) {
            $out .= stream_get_contents($pipes[1]);
            $err .= stream_get_contents($pipes[2]);
            $status = proc_get_status($proc);
            if (!$status['running']) {
                $out .= stream_get_contents($pipes[1]);
                break;
            }
            if (time() > $deadline) {
                proc_terminate($proc);
                $status['exitcode'] = -1;
                break;
            }
            usleep(50000);
        }
        fclose($pipes[1]);
        fclose($pipes[2]);
        proc_close($proc);
        if ($status['exitcode'] !== 0) {
            error_log('converter failed: ' . implode(' ', $args) . "\n" . $err);
        }
        return [$status['exitcode'], $out];
    }
}
