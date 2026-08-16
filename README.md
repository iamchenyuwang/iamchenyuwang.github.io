# Chenyu Wang — Academic Website

A static, single-page academic website. The homepage contains the research profile,
news, publications, education, teaching, and community work in one dense reading flow.

## Structure

```text
index.html          # Main academic profile and publication record
home.css            # Homepage layout and responsive styles
home.js             # Mobile navigation and active-section behavior
papers.html         # Standalone searchable community paper collection
papers.js           # Paper collection filtering and chart logic
styles.css          # Legacy styles used by the paper collection
assets/             # Profile image, PDFs, and other static files
Chenyu_Wang_Resume.pdf # Current one-page resume
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
- Replace `Chenyu_Wang_Resume.pdf` to update the resume linked from the homepage.
- The searchable reading list is generated from the JSON files in `_data/`.

## Contact

- Email: chenyu_wang@seas.harvard.edu
- [Google Scholar](https://scholar.google.com/citations?user=QI96hfoAAAAJ&hl=en)
