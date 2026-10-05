<?php
declare(strict_types=1);

/** The two Stripe calls the site needs, over plain HTTPS (no SDK, so no Composer on the server). */
final class Stripe
{
    public static function enabled(): bool
    {
        return config('stripe_secret_key') !== '';
    }

    /** Starts a hosted Stripe Checkout page for one piece; returns the URL to send the buyer to. */
    public static function checkoutUrl(Job $job): string
    {
        $base = config('base_url');
        $session = self::api('POST', 'checkout/sessions', [
            'mode' => 'payment',
            'line_items[0][quantity]' => 1,
            'line_items[0][price_data][currency]' => config('currency'),
            'line_items[0][price_data][unit_amount]' => config('price_pence'),
            'line_items[0][price_data][product_data][name]' => 'Letter-note sheet music: ' . $job->title(),
            'client_reference_id' => $job->id,
            'metadata[job]' => $job->id,
            'success_url' => "$base/paid.php?id={$job->id}&session={CHECKOUT_SESSION_ID}",
            'cancel_url' => "$base/view.php?id={$job->id}",
        ]);
        return $session['url'];
    }

    /** True when this Checkout session was paid for this piece. */
    public static function sessionPaidFor(string $sessionId, Job $job): bool
    {
        if (!preg_match('/^cs_[A-Za-z0-9_]+$/', $sessionId)) {
            return false;
        }
        $s = self::api('GET', 'checkout/sessions/' . $sessionId);
        return ($s['payment_status'] ?? '') === 'paid' && ($s['client_reference_id'] ?? '') === $job->id;
    }

    /** Checks the Stripe-Signature header of a webhook call; returns the event or null. */
    public static function webhookEvent(string $payload, string $header): ?array
    {
        $secret = config('stripe_webhook_secret');
        if ($secret === '' || !preg_match('/t=(\d+)/', $header, $t)) {
            return null;
        }
        preg_match_all('/v1=([a-f0-9]+)/', $header, $sigs);
        $expected = hash_hmac('sha256', $t[1] . '.' . $payload, $secret);
        $valid = false;
        foreach ($sigs[1] as $sig) {
            $valid = $valid || hash_equals($expected, $sig);
        }
        if (!$valid || abs(time() - (int) $t[1]) > 600) {
            return null;
        }
        return json_decode($payload, true);
    }

    private static function api(string $method, string $path, array $params = []): array
    {
        $ch = curl_init('https://api.stripe.com/v1/' . $path);
        curl_setopt_array($ch, [
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_USERPWD => config('stripe_secret_key') . ':',
            CURLOPT_TIMEOUT => 20,
        ]);
        if ($method === 'POST') {
            curl_setopt($ch, CURLOPT_POSTFIELDS, http_build_query($params));
        }
        $res = json_decode((string) curl_exec($ch), true) ?: [];
        curl_close($ch);
        if (isset($res['error'])) {
            throw new RuntimeException('Stripe: ' . ($res['error']['message'] ?? 'error'));
        }
        return $res;
    }
}
