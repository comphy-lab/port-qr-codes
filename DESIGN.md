# QR-code design and migration ledger

## Design rules

- Authoritative artwork is SVG with a quiet zone retained around the code.
- Purple `#67236C` on white is the current CoMPhy treatment.
- A logo may only occupy the error-correction budget; every rendered variant
  must be decoded before publication.
- Public first-party destinations are preferred. A short redirect is allowed
  only when its destination is documented here and controlled by CoMPhy Lab.

## Known migration

| Legacy code | Replacement | Status |
| --- | --- | --- |
| `https://qrco.de/beQCcR` | `https://comphy-lab.org/contact-card/` | Replaced; the destination offers the contact card and vCard download. |

## Historical assets

`legacy/` retains the existing SVG collection in its original folder layout.
It is intentionally not a claim that the embedded targets are current. Each
asset gets a dedicated entry here after its payload, ownership, and current
destination have been verified.
