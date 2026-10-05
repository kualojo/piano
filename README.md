# Letter Notes

Upload piano sheet music as a PDF; get it back with the letter name of every note written in
(right hand red above the staff, left hand blue below; flat = letter in a square, sharp = letter in a circle),
plus playback and a piano roll. Free preview of the first lines, pay to unlock the whole piece.

## How it fits together

| Part | What it does |
| --- | --- |
| `converter/letternotes.py` | Reads a notation-software PDF (Sibelius / Opus font) directly: staves, barlines, noteheads, clefs, key signatures, accidentals, ties, beams, flags, dots, triplets. Writes the lettered PDF, a preview of the first N lines (PDF + PNG) and `notes.json` (pitch, letter name, hand, onset and length in beats) for playback. |
| `converter/checkpdf.py` | Quick check before converting: is this a PDF we can read, or a scan / unsupported engraver? |
| `public/` | The PHP site (document root). `upload.php` → `view.php` (preview image + player) → `checkout.php` (Stripe Checkout) → `paid.php` / `stripe-webhook.php` mark the piece paid → `download.php`. |
| `public/assets/player.js` | Playback with Tone.js (bundled) and the Salamander piano samples, drawn as a piano roll with letter names; hands can be muted to practise one at a time. |
| `src/` | Plain PHP 8.1+, no Composer: jobs on disk under `storage/jobs/<random id>/`, the Python runner, two Stripe API calls. |
| `scripts/server-setup.sh` | Run by the deploy on the server: finds Python 3.9+, builds `.venv` with PyMuPDF, creates `config.php`, schedules the clean-up cron, and prints what the server can run. |

The free preview is enforced on the server: unpaid pieces only ever send the preview image and the
preview lines' notes to the browser.

## Run it locally

```sh
python3 -m venv .venv && .venv/bin/pip install -r converter/requirements.txt
cp config.example.php config.php    # set 'demo_unlock' => true to test without Stripe
php -S 127.0.0.1:8099 -t public
```

## Deploy

See [docs/cpanel-setup.md](docs/cpanel-setup.md). Pushing to `main` deploys over SSH with GitHub Actions.

## Known limits (proof of concept)

- Only PDFs exported from Sibelius (Opus music font). Other engravers need their font's glyph map; scans need OMR.
- Playback timing is read from the notation and fitted to each bar; repeats, 8va lines and swing are not applied yet.
