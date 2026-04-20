# Sample input dataset

SWUIFT needs ten `.mat` files to run (see
[README §3.1 — Data Inputs](README.md#31-tab-1--data-inputs)).  Because
the wind file is ~7 GB, the full set is **not** committed to this
repository — it is published as a GitHub Release.

Total download: **~7 GB** (extracted).  Plan your disk and bandwidth
accordingly.

## Quick start

From the repository root:

```bash
./scripts/fetch_sample_data.sh
```

This downloads every asset from the latest sample-data release, verifies
SHA-256 checksums, extracts the small `.mat` bundle, reassembles
`wind.mat` from its split chunks, and leaves everything under
`extracted_mat/`.  Point Tab 1 of the SWUIFT GUI at that folder.

Override the destination or pin a different release tag:

```bash
DEST=/tmp/swuift-data ./scripts/fetch_sample_data.sh
TAG=sample-data-v2    ./scripts/fetch_sample_data.sh
```

## Release assets

Published at
[github.com/utkrshkmr/swuift-py-app/releases](https://github.com/utkrshkmr/swuift-py-app/releases)
under the tag `sample-data-v1`:

| Asset                       | Approx. size | Contents                                                            |
| --------------------------- | -----------: | ------------------------------------------------------------------- |
| `extracted_mat_small.tar.gz`|    ~75 MB    | 9 small input rasters (all `.mat` files except `wind.mat`)          |
| `wind.mat.part.aa`          |    1.90 GB   | chunk 1 of 4 of `wind.mat`                                          |
| `wind.mat.part.ab`          |    1.90 GB   | chunk 2 of 4                                                        |
| `wind.mat.part.ac`          |    1.90 GB   | chunk 3 of 4                                                        |
| `wind.mat.part.ad`          |    ~1.1 GB   | chunk 4 of 4                                                        |
| `SHA256SUMS`                |      <1 KB   | integrity manifest for every asset + the reassembled `wind.mat`     |

### Manual download / reassembly

If you'd rather not run the helper script:

```bash
mkdir -p extracted_mat && cd extracted_mat

BASE=https://github.com/utkrshkmr/swuift-py-app/releases/download/sample-data-v1
for f in SHA256SUMS extracted_mat_small.tar.gz wind.mat.part.aa wind.mat.part.ab \
         wind.mat.part.ac wind.mat.part.ad; do
    curl -LO "$BASE/$f"
done

shasum -a 256 -c SHA256SUMS          # expect every line to print "OK"
tar -xzf extracted_mat_small.tar.gz  # 9 small .mat files
cat wind.mat.part.* > wind.mat       # reassemble
rm wind.mat.part.* extracted_mat_small.tar.gz
```

## Publishing a new dataset (maintainers)

The [`scripts/prepare_sample_data_release.sh`](scripts/prepare_sample_data_release.sh)
helper automates the split / hash / upload workflow.  It expects:

- the full, uncompressed `extracted_mat/` present locally, including
  `wind.mat`;
- [GitHub CLI](https://cli.github.com) installed and authenticated
  (`gh auth login`).

```bash
./scripts/prepare_sample_data_release.sh              # tag = sample-data-v1
TAG=sample-data-v2 ./scripts/prepare_sample_data_release.sh
```

The script:

1. `tar -czf` the small `.mat` files into `extracted_mat_small.tar.gz`.
2. `split -b 1900m` the `wind.mat` file into `wind.mat.part.aa…ad`.
3. `shasum -a 256` every asset plus the reassembled `wind.mat` into
   `SHA256SUMS`.
4. `gh release create` (if needed) and `gh release upload --clobber` all
   assets under the chosen tag.

Because the upload moves ~7 GB to GitHub, expect this step to take
**several hours** on residential broadband — run it in a shell that
won't be closed (e.g. `tmux` / `screen`).

## Why not Git LFS?

GitHub's Git LFS per-file limit is 2 GB on free plans (5 GB on Pro),
and `wind.mat` is 6.8 GB — it cannot be stored in LFS at all.  Release
assets have their own 2 GB per-file cap, so the wind file is split into
four sub-2 GB chunks and reassembled on download.

Release assets also don't count against GitHub's 1 GB free LFS
storage/bandwidth quota, which matters for a dataset this size.
