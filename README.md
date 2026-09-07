# CoMPhy Lab QR codes

This public repository is the durable source for CoMPhy Lab QR artwork and its
migration ledger. The inventory covers all 69 codes observed in the source
account: 14 active dynamic codes, four paused dynamic codes, and 51 static
codes. Private targets are counted but redacted.

Browse the [QR download catalogue](https://comphy-lab.org/port-qr-codes/)
for SVG and PNG downloads of all 63 public, non-paused account codes. The three
[standalone branded codes](current/) also include both formats.

The known contact-card replacement is
[`https://comphy-lab.org/contact-card/`](https://comphy-lab.org/contact-card/),
which supersedes the third-party dynamic code `https://qrco.de/beQCcR`.

## Layout

- `inventory/codes.json`: authoritative, privacy-filtered account inventory.
- `scripts/`: validation, deterministic generation, and QR decode checks.
- `requirements-lock.txt`: complete, hashed contributor and CI dependencies.
- `current/account/`: generated replacements for public account codes.
- `site/`: generated first-party landing pages for multi-link codes.
- `make_branded_qr_codes.py`: reproducible bespoke branded assets.
- `assets/`: public branding input used by the generator.
- `assets/fonts/`: self-hosted SIL OFL web fonts, copied verbatim into
  `site/assets/fonts/` so the pages make no third-party request.
- `legacy/`: preserved SVG artwork from the historic Dropbox collection.
- `DESIGN.md`: asset design and migration rules.

## Rebuild

```bash
python3 -m pip install --require-hashes -r requirements-lock.txt
python3 scripts/validate_inventory.py
python3 scripts/generate.py --check
python3 -m unittest discover -v
```

Run `python3 scripts/generate.py` to refresh the generated account artwork and
landing pages after an inventory change. The bespoke generator needs
`rsvg-convert` for PNG/PDF derivatives; it uses
`assets/comphy-lab-mark.png` by default and accepts `COMPHY_QR_MARK` as a
portable override.

## Published destinations

GitHub Pages publishes `site/` at `https://comphy-lab.org/port-qr-codes/` after
inventory, generation, and decode checks pass on `main`. Each deployment
fetches every published page and QR download and checks them against the
validated source. SVG bytes and decoded PNG pixels must match exactly, allowing
lossless PNG recompression. HTML permits only the hosting provider's known
Cloudflare beacon insertion. The strict page CSP is preserved; it is
`default-src 'none'` with `img-src`, `style-src` and `font-src` limited to
`'self'`, so the pages stay script-free and make no cross-origin request.
Run `python3 scripts/verify_deployment.py` to repeat that
live deployment check.

Single-destination routes are minimal stubs: a meta refresh to the documented
target, `robots: noindex`, a canonical pointing at that target rather than at
the stub, and one manual link if the refresh does not fire. They carry no QR
panel and no download pills, because the refresh removes the document before
either could be used; both formats stay reachable from the catalogue card.
Collections retain their individual links on a full landing page. The
`bursting-bubble-paper` route points to the **2021 viscoplastic paper**;
`arxiv-bursting-bubbles-ve` directly encodes the **2025 viscoelastic paper's
arXiv PDF**, `https://arxiv.org/pdf/2408.05089`.

The four paused codes remain historical entries without replacement artwork;
the two private static codes remain redacted. `legacy/` preserves the original
images, including old vendor URLs. Use `current/` for new artwork.

## Cutover boundary

An already printed dynamic code still encodes its historical `qrco.de` URL.
No repository change can rewrite that physical payload. Migration therefore
means preserving the old evidence, publishing and verifying the replacement,
then replacing the artwork wherever it is printed or embedded. The former
`qr.comphy-lab.org` payloads used an unconfigured subdomain. Replace those
images with the corresponding files in `current/account/`, which use the
published `comphy-lab.org/port-qr-codes/` routes. Existing printed images cannot
be repaired by changing an SVG in this repository.
