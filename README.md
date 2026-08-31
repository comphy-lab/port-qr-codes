# CoMPhy Lab QR codes

This public repository is the durable source for CoMPhy Lab QR artwork and its
migration ledger. The inventory covers all 69 codes observed in the source
account: 14 active dynamic codes, four paused dynamic codes, and 51 static
codes. Private targets are counted but redacted.

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

## Cutover boundary

An already printed dynamic code still encodes its historical `qrco.de` URL.
No repository change can rewrite that physical payload. Migration therefore
means preserving the old evidence, publishing and verifying the replacement,
then replacing the artwork wherever it is printed or embedded. Generated
`qr.comphy-lab.org` pages in this repository are prepared source, not a claim
that DNS or hosting is already live.
