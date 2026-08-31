# Image attribution

The landing page images are downloaded once and committed, so the running
application has no external image dependency. They are not hot-linked.

**Source:** [Unsplash](https://unsplash.com), used under the
[Unsplash License](https://unsplash.com/license), which permits free use for
commercial and non-commercial purposes without permission. Attribution is not
required by the licence; it is recorded here as good practice and so the
provenance of every asset in this repository is traceable.

| File | Unsplash photo | Used for |
|------|----------------|----------|
| `feature-01.jpg` | `photo-1476514525535-07fb3b4ae5f1` | Trips & Itinerary |
| `feature-02.jpg` | `photo-1414235077428-338989a2e8c0` | Attractions & Dining |
| `feature-03.jpg` | `photo-1522202176988-66273c2fd55f` | Travel Mate |
| `feature-04.jpg` | `photo-1488646953014-85cb44e25828` | Account & Dashboard |
| `feature-05.jpg` | `photo-1436491865332-7a61a109cc05` | Bookings & Budget |
| `hero.jpg` | `photo-1506905925346-21bda4d32df4` | Hero background |

Re-fetch with `python3 scripts/fetch_assets.py`. That script is for maintenance
only - it is never run at build or deploy time, and it will not overwrite a
committed image if the download fails.

## Why these are committed rather than fetched

The original design hot-linked `picsum.photos`. On 31 August 2026 that service
returned 503 and every image on the home page broke, six days before the
Release 0 submission. Our network was fine; the third party was not. Recorded as
risk R9 in the technical report.
