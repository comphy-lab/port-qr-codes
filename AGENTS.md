# port-qr-codes

## Purpose

Public, reproducible custody for CoMPhy Lab QR-code artwork and its migration
away from third-party dynamic QR services.

## Handling

- Commit SVG sources and `DESIGN.md` records. Generated PNG/PDF derivatives
  are allowed when they are useful for print or publication workflows.
- Each migrated code must use a durable first-party URL and be verified by
  decoding the rendered SVG before it replaces a live third-party code.
- `legacy/` is an evidence archive, not proof that every historical target is
  still desirable or live. Do not silently redirect or retire a code.
- Do not add private contact details, analytics credentials, or unpublished
  destinations to this public repository.
