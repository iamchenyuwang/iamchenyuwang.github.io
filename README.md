# Chenyu Wang — Academic Website

A static, single-page academic website. The homepage contains the research profile,
news, publications, and professional service in one reading flow.

## Structure

```text
index.html          # Main academic profile and publication record
home.css            # Homepage layout and responsive styles
assets/             # Profile image, PDFs, and other static files
```

Legacy URLs `publications.html` and `blog.html` redirect into the single-page site so
existing external links continue to work.

## Local preview

Run a static server from the repository root:

```bash
python3 -m http.server 8000
```

Then open `http://localhost:8000`.

There is no build step. GitHub Pages can serve the repository directly.

## Updating content

- Edit profile, news, publications, and experience in `index.html`.
- Replace `assets/images/profile.jpg` to update the portrait.
## Publication updates

A local monthly cron job starts a fresh Codex review using
`scripts/run_monthly_publication_agent.sh`. The agent searches current primary
sources, checks each candidate against Chenyu's research identity and established
collaborators, and may edit the News and Publications sections of a throwaway
copy of the site. The durable review instructions live in
`automation/monthly_publication_prompt.md`; run logs are written to the ignored
`logs/monthly-publications/` directory.

Because the agent reads untrusted web content, it runs in a transient systemd
sandbox that sees only that copy, its Codex login, and the network: no other
projects, SSH keys, GitHub tokens, host sockets, or root capabilities. The
wrapper script, not the agent, then checks the edit with
`scripts/validate_publication_diff.py` (only News and Publications may change,
using the existing markup and HTTPS links) before it commits, pushes, and
confirms the live page.

To run the same review manually, or without publishing:

```bash
./scripts/run_monthly_publication_agent.sh
./scripts/run_monthly_publication_agent.sh --dry-run
```

To install or refresh the server schedule (first day of every month at 14:17
UTC), run:

```bash
./scripts/install_monthly_publication_cron.sh
```

## Contact

- Email: chenyu_wang@seas.harvard.edu
- [Google Scholar](https://scholar.google.com/citations?user=QI96hfoAAAAJ&hl=en)
