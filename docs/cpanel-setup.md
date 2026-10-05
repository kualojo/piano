# cPanel setup

The site deploys from GitHub Actions over SSH with a key made only for deploys. Its private half
lives only in GitHub's encrypted secrets; it is never pasted into chat or committed.

1. **Account and domain.** Create the cPanel account. When you add the domain or subdomain, set its
   **Document Root** to `piano/public` (the deploy puts the app in `~/piano`; only `public/` is web-visible).
2. **Deploy key.** On your own computer:
   `ssh-keygen -t ed25519 -C piano-deploy -f piano_deploy -N ""`
3. **Authorise it in cPanel.** *SSH Access → Manage SSH Keys → Import Key*: name `piano_deploy`, paste
   only `piano_deploy.pub`. Then *Manage → Authorize*. Make sure the account has shell access.
4. **Give GitHub the private half.** *github.com/kualojo/piano → Settings → Secrets and variables →
   Actions → New repository secret*: name `DEPLOY_SSH_KEY`, value = contents of `piano_deploy`.
   Then delete both files from your computer.
5. **Server details.** Put the hostname, SSH port and cPanel username in the `env:` block of
   `.github/workflows/deploy.yml` (not secret).
6. **Deploy.** Push to `main`, or run *Actions → Deploy to cPanel → Run workflow*. The last step
   prints PHP/Python versions and whether `proc_open` is allowed.
7. **Config.** The first deploy creates `~/piano/config.php`. Set `base_url`, and later the Stripe keys.
   For Stripe, add a webhook for `checkout.session.completed` pointing at `https://<domain>/stripe-webhook.php`.

If no Python 3.9+ is found, create one with *Setup Python App* (Python 3.11) and deploy again;
the setup script picks it up.
