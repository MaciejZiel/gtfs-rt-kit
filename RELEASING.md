# Releasing

Releases are published to PyPI by [`.github/workflows/release.yml`](.github/workflows/release.yml)
using [Trusted Publishing](https://docs.pypi.org/trusted-publishers/) (OpenID Connect):
GitHub proves the identity of the workflow to PyPI, so no API token is stored in the
repository or its secrets. The workflow runs when a tag like `v0.1.0` is pushed; it runs
the tests, builds the sdist and wheel, checks that the tag matches
`gtfs_rt_kit.__version__`, uploads to PyPI and creates a GitHub release with the
matching CHANGELOG section.

## One-time setup

### 1. Register the trusted publisher on PyPI

The project does not exist on PyPI yet, so it is registered as a *pending* publisher;
the first successful upload creates it.

1. Sign in at <https://pypi.org> (enable two-factor authentication if asked).
2. Open your account menu (top right) and click **Your account**, then **Publishing** in
   the left sidebar (direct link: <https://pypi.org/manage/account/publishing/>).
3. Under **Add a new pending publisher**, select the **GitHub** tab and fill in exactly:

   | Field | Value |
   | --- | --- |
   | PyPI Project Name | `gtfs-rt-kit` |
   | Owner | `MaciejZiel` |
   | Repository name | `gtfs-rt-kit` |
   | Workflow name | `release.yml` |
   | Environment name | `pypi` |

4. Click **Add**. The entry appears under **Pending publishers**.

A pending publisher does not reserve the name: publish soon after adding it. Once the
first release is uploaded the entry moves to the project's own
**Manage → Publishing** page.

### 2. Create the `pypi` environment on GitHub (recommended)

1. In the repository, open **Settings → Environments → New environment**.
2. Name it `pypi` and click **Configure environment**.
3. Optional but recommended: under **Deployment protection rules** tick
   **Required reviewers** and add yourself, so every upload waits for your approval;
   under **Deployment branches and tags** choose **Selected branches and tags** and add
   the tag rule `v*`.
4. Click **Save protection rules**.

(If the environment does not exist, GitHub creates it without protection rules on the
first run.)

## Publishing a release

1. Make sure CI on `main` is green.
2. Bump `__version__` in `src/gtfs_rt_kit/__init__.py` following
   [Semantic Versioning](https://semver.org/): patch for fixes, minor for new
   backwards-compatible features, major for breaking changes.
3. In `CHANGELOG.md`, move the entries from **Unreleased** to a new
   `## [X.Y.Z] - YYYY-MM-DD` section and update the comparison links at the bottom.
4. Commit, open a pull request, and merge it once CI passes.
5. Tag the merge commit and push the tag:

   ```bash
   git checkout main && git pull
   git tag -a vX.Y.Z -m "vX.Y.Z"
   git push origin vX.Y.Z
   ```

6. Watch **Actions → Release**. If you configured required reviewers, approve the
   `pypi` deployment. The package then appears at <https://pypi.org/project/gtfs-rt-kit/>
   and a GitHub release is created with the built files attached.

If the version check fails, delete the tag (`git push --delete origin vX.Y.Z` and
`git tag -d vX.Y.Z`), fix the version and tag again. Versions uploaded to PyPI can never
be replaced, only yanked, so a mistake means releasing the next patch version.

## Documentation

The docs site is built on every push and deployed to GitHub Pages from `main` when the
repository is public. To enable it once: **Settings → Pages → Build and deployment →
Source: GitHub Actions**, then re-run the **Docs** workflow (**Actions → Docs → Run
workflow**). The site is served at <https://maciejziel.github.io/gtfs-rt-kit/>.
