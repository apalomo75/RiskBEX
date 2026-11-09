# Sprint 9B — Updater prerequisites

Validated on 2026-11-09. No market download, training, container launch, scheduler
activation, installation or commit was performed. Sprint 9A changes are preserved.

## Corrections and exact configured inputs

The existing `.env` and Compose paths now resolve without configuration changes:

| Purpose | Host path relative to repository | Container path |
|---|---|---|
| Store | `backend/runtime/main-wsl-test` | `/app/runtime/main` |
| Seed | `backend/runtime/inputs/seed.csv` | `/inputs/seed.csv` |
| Receipt | `backend/runtime/inputs/receipt.json` | `/inputs/receipt.json` |

All host paths resolve beneath `/home/apalo/projects/RiskBEX`. Runtime inputs and
`.env` are Git-ignored; they must be preserved on the operator's host. They are
not shipped by a Git checkout or baked into the image.

The seed is an exact decompression of the existing `historical_prices.csv.gz`
fixture, whose manifest records original TFM Git source
`8dd66a93c06dc3cbfaac29f086ad2625d32d9756:data/raw/ibex_prices.csv`.
Its SHA-256 is `8a7ce329e83eefd32266a88d17b02a641998ab26c891af72eedda70fef44ed12`.
It contains 6,690 rows, 2000-01-04 through 2026-04-23, with `date`, `ibex_close`
and the pre-existing `ret_1d` column. The pipeline consumes the first two and
recomputes indicators. No synthetic extension or published output was used to
create the seed. Validation checked fixture hash, dates/numeric/positive-price
rules, frozen training prefix, 2026 exchange continuity, exact canonical price
agreement with the current publication's historical prefix and CSV round-trip.
Pre-2026 provenance rests on the approved frozen reference and training prefix;
no unreviewed historical calendar was introduced. Evidence is in ignored
`backend/runtime/inputs/seed-validation.json`.

## Receipt root cause and actual regression

The historical receipt's loader hash matches commit `41bac61`. The complete change
to that file in `f218d99` adds only `turnover.csv` to `load_operational_results`.
It affects result consumption, not historical price loading, signal generation,
backtest generation or VersionStore validation. The pipeline hash inventory
includes every pipeline Python file, so this adapter change invalidated the gate.
No implementation or integrity control was changed to resolve it.

Executed from `backend` with the approved runtime:

```bash
/home/apalo/miniconda3/envs/fin-forecasting/bin/python -B scripts/check_daily_regression.py \
  --output runtime/inputs/receipt.json
```

The existing verifier passed against frozen references before writing the new
receipt: 1,357 signals and 1,356 realised rows, 2021-01-05 through 2026-04-23.
Maximum errors: features `4.13e-13`, causal predictions `0`, causal backtests
`1.29e-14`, regime backtests `1.53e-16`. The original academic comparison retains
its previously approved 11 classification differences and maximum Markov
probability difference `0.0009267752` (limit `0.002`). `verify_gate` independently
accepted the generated receipt with the current package and implementation hashes.
The historical receipt and model artifacts were not modified.

## Configuration, verification and remaining limits

- Compose rendered successfully. Assertions confirmed seed/receipt read-only,
  updater store read/write, API store read-only, matching store source and
  dashboard API URL. UID/GID 1000 matches the writable host store. This establishes
  container mount policy; it does not prohibit authorized host writes.
- MAIN package and required runtime/library versions passed validation using
  Python 3.11.14. All four existing container scheduler tests passed.
- The store pointer digest is unchanged and the published version still validates:
  `729b9de228fd3e9100e95e93a81301590a17341f6033078db6e470a115e31335`,
  market session 2026-11-06. No update or publication was performed.
- Compose normalizes read/write mounts by omitting `read_only`; the initial
  ad-hoc assertion incorrectly required an explicit false value. The corrected
  check uses Compose's default and passed. No Compose change was necessary.
- No full quantitative suite or unrelated UI tests ran. `git diff --check` passed.

The [official BME calendar](https://www.bolsasymercados.es/en/bme-exchange/trading/trading-calendar.html)
was checked and still lists 2026. A targeted search did not verify an authoritative
2027 SIBE calendar. Coverage remains **2026 only**, with 2027 rejected by the
existing calendar. Once the official 2027 calendar/operating instruction is
available, review its exchange-specific closures and shortened sessions, extend
`years` and `holidays` with source/review metadata, test year-boundary eligibility
and next-session calculation, and rebuild the shared API/updater image. Do not
substitute civil holidays or another exchange's calendar. Coverage is required
before publishing a signal targeting the first 2027 session.

The reproducible local input blockers are resolved for 2026. A controlled live test
still needs operator authorization, Docker daemon access, image/runtime and bind
permission validation, live Yahoo access and confirmation that no host/container
scheduler is already active. Sprint 9A could not inspect systemd/cron/Docker because
of permissions; those remain unverified, not assumed absent. This sprint activated
no second scheduler. Use the existing entry point and operator procedure in
`sprint-9a.md`; do not add a manual download workflow. A successful live one-shot
would not establish autonomy: a future scheduled run must complete without operator
intervention. No such run has been observed.
