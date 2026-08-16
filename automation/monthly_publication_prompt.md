# Monthly publication audit

You are maintaining Chenyu Wang's academic homepage in this Git repository.
This is an unattended monthly audit. There is no user available to answer
questions during the run.

Your task is to research whether Chenyu has any new AI-related papers that are
missing from `index.html`. Do the identity review yourself; do not accept the
output of an author-name search or a repository script as proof.

## Identity and evidence rules

- The author must be the Chenyu Wang whose homepage is this repository and who
  is a Harvard PhD student. Read `index.html` and, when useful,
  `Chenyu_Wang_Resume.pdf` to understand the existing research record.
- There are many researchers named Chenyu Wang. Prefer missing a paper over
  adding another person's paper.
- Search current primary sources on the web, including arXiv, official venue or
  project pages, and author/lab publication pages. A Google Scholar result can
  help discover a candidate but is not sufficient identity evidence by itself.
- Chenyu's papers are generally about AI and commonly include Yilun Du or Vijay
  Janapa Reddi as a coauthor. Either coauthor is strong identity evidence. A
  paper without either name requires other concrete evidence linking it to this
  Chenyu, such as matching Harvard affiliation, a project page from the same
  research group, or continuity with several established collaborators and the
  research topics on the homepage.
- Verify the exact title, complete author list, year, canonical paper URL, and
  publication venue/status from primary sources before editing.
- Never add citation counts or other scholar metrics.

## Editing and publishing rules

- If there is no high-confidence missing paper, do not modify any files and do
  not create a commit.
- If there is a high-confidence missing paper, edit only the publication record
  in `index.html`. Preserve the existing plain, dense academic design and its
  current HTML conventions. Do not redesign the site or change unrelated copy.
- Avoid duplicates by comparing normalized titles and canonical URLs.
- Review the rendered HTML or run a suitable local check before publishing.
- Inspect the final diff. Commit only the intended publication addition with a
  concise commit message, then push it to `origin/main`, as the owner has
  explicitly authorized direct publication updates.
- After pushing, use the available GitHub tooling to check the Pages deployment
  and verify the live homepage when possible. Do not rewrite history or force
  push.

In your final response, report what sources you checked, each candidate you
considered and the identity evidence for it, whether files changed, the commit
hash if one was pushed, and the deployment result. Keep the report concise but
specific so it can be audited from the local log.
