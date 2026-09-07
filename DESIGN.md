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

## Migration states

- `replacement-ready`: a public active dynamic code has a reviewed replacement
  payload and generated artwork. First-party pages still need a deployment
  receipt before physical cutover.
- `direct-static`: the original code already has a clear public destination;
  the replacement encodes that destination directly.
- `source-preserved`: a paused code or obsolete event asset is retained as
  evidence but is not promoted as a live destination.
- `private-redacted`: the account entry is counted, but its destination and
  artwork remain outside this public repository.

Every active dynamic replacement uses
`https://comphy-lab.org/port-qr-codes/<slug>/` as its stable payload.
These static, script-free pages preserve the
ability to update a destination without depending on a paid QR provider; all
outbound links must be explicit HTTPS URLs. Existing static codes continue to
encode their canonical destinations directly.

Each public, non-paused account code is distributed as a matching SVG and PNG
pair. Single-destination pages automatically open their documented target;
multi-link pages present their collection. The download catalogue provides
both formats without requiring a visit to the redirect page. Bespoke branded
artwork in `current/` also includes PNG derivatives of its SVG sources.

## Historical assets

`legacy/` retains the existing SVG collection in its original folder layout.
It is intentionally not a claim that the embedded targets are current. Each
asset gets a dedicated entry here after its payload, ownership, and current
destination have been verified.
