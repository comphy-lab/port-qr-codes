# CoMPhy Lab QR codes

This public repository is the durable source for CoMPhy Lab QR artwork and its
migration ledger. It replaces dependence on paid dynamic-QR hosting with
first-party destinations under `comphy-lab.org` where applicable.

The known contact-card replacement is
[`https://comphy-lab.org/contact-card/`](https://comphy-lab.org/contact-card/),
which supersedes the third-party dynamic code `https://qrco.de/beQCcR`.

## Layout

- `make_branded_qr_codes.py`: reproducible branded assets.
- `assets/`: public branding input used by the generator.
- `legacy/`: preserved SVG artwork from the historic Dropbox collection.
- `DESIGN.md`: asset design and migration rules.

## Rebuild

```bash
python3 -m pip install -r requirements.txt
python3 make_branded_qr_codes.py
```

The generator needs `rsvg-convert` to make PNG and PDF derivatives. Set
`COMPHY_QR_MARK` only when using a different public CoMPhy logo input.
