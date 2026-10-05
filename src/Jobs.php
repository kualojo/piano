<?php
declare(strict_types=1);

/** One uploaded piece: its files live in storage/jobs/<id>/, its state in meta.json. */
final class Job
{
    public function __construct(public readonly string $id, public array $meta)
    {
    }

    public function dir(): string
    {
        return Jobs::root() . '/' . $this->id;
    }

    public function file(string $name): string
    {
        return $this->dir() . '/' . $name;
    }

    public function paid(): bool
    {
        return !empty($this->meta['paid']);
    }

    public function title(): string
    {
        return $this->meta['title'] ?? 'Your piece';
    }

    public function save(): void
    {
        file_put_contents($this->file('meta.json'), json_encode($this->meta, JSON_PRETTY_PRINT), LOCK_EX);
    }

    public function markPaid(string $reference): void
    {
        $this->meta['paid'] = true;
        $this->meta['paid_at'] = date('c');
        $this->meta['payment_ref'] = $reference;
        $this->save();
    }
}

final class Jobs
{
    public static function root(): string
    {
        return APP_ROOT . '/storage/jobs';
    }

    public static function create(array $meta): Job
    {
        $id = bin2hex(random_bytes(16));   // the id is the secret link, so it must be unguessable
        mkdir(self::root() . '/' . $id, 0700, true);
        $job = new Job($id, $meta + ['created' => date('c'), 'paid' => false]);
        $job->save();
        return $job;
    }

    public static function find(string $id): ?Job
    {
        if (!preg_match('/^[a-f0-9]{32}$/', $id)) {
            return null;
        }
        $metaFile = self::root() . "/$id/meta.json";
        if (!is_file($metaFile)) {
            return null;
        }
        return new Job($id, json_decode((string) file_get_contents($metaFile), true) ?: []);
    }

    /** Delete pieces older than keep_days. Run from cron: php scripts/cleanup.php */
    public static function cleanup(int $days): int
    {
        $n = 0;
        foreach (glob(self::root() . '/*/meta.json') as $metaFile) {
            if (filemtime($metaFile) < time() - $days * 86400) {
                self::removeDir(dirname($metaFile));
                $n++;
            }
        }
        return $n;
    }

    private static function removeDir(string $dir): void
    {
        foreach (scandir($dir) ?: [] as $f) {
            if ($f !== '.' && $f !== '..') {
                is_dir("$dir/$f") ? self::removeDir("$dir/$f") : unlink("$dir/$f");
            }
        }
        rmdir($dir);
    }
}
