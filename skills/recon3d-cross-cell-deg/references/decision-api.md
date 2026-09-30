# Optional decision API integration

The API bridge requires Python 3.10+ and the standard library only. It implements the [TypeSafe HTTP contract](https://docs.typesafe.ai/api), checked 2026-09-30: `POST /v1/systemone`, `GET /v1/models`, Bearer authentication, and typed `noul`, `choice`, `score` questions. It is not a chat-completions client.

## Hosted Jev

Set `TYPESAFE_API_KEY` in the process environment (`JEV_API_KEY` is an accepted alias). Do not put a real key in a request JSON, a repository, or a prompt. The default API base is `https://api.typesafe.ai/v1`; the default model is `jev-latest`. For reproducible comparisons, pin a version from the [model documentation](https://docs.typesafe.ai/models). Every response retains the actual resolved model and token usage.

Run commands from the installed skill directory:

```sh
python3 scripts/recon3d.py models --provider jev
python3 scripts/recon3d.py evaluate --input request.json --output response.json
python3 scripts/recon3d.py prioritize --input candidates.json --output priorities.json
```

`request.json` has exactly `model`, `state`, and `questions`; it uses the official contract. A candidate file is an array of objects with unique string `id` and text/object/array `summary`. Extra candidate fields are preserved locally and are not sent to the API. The summary itself is sent to the selected endpoint.

## Laya or another compatible server

For a Jev-compatible Laya server, choose the model it actually serves:

```sh
python3 scripts/recon3d.py models --provider laya --base-url http://127.0.0.1:8000/v1
python3 scripts/recon3d.py prioritize --provider laya --model laya \
  --base-url http://127.0.0.1:8000/v1 --input candidates.json --output priorities.json
```

`--provider laya` defaults to `http://127.0.0.1:8000/v1` and reads only `LAYA_API_KEY`; it does not reuse the hosted Jev key. Authentication can be omitted for a loopback server. Remote endpoints require HTTPS and a key. The bridge sends the full supplied summary; it never silently truncates input. A server may have a smaller model context or perform its own truncation: check the server and checkpoint configuration separately. A common wire format does not make Jev and Laya probabilities, calibration, or performance equivalent. See the [Laya source](https://github.com/NandhaKishorM/laya).

## Interpretation and failures

- Review guidance only orders the supplied candidate queue. It does not enumerate paths, compute GPR proxies, run patient-level tests, or establish transfer or flux.
- All candidates remain in the output, including failed API calls. All scientific `review_status` values remain `pending`; `review_complete` remains `false`.
- `guidance_complete` describes successful API scoring of every supplied candidate, not exhaustive route enumeration or scientific review.
- Before the first call and after each attempted candidate, the CLI atomically saves the full report. Interruption leaves scored and pending candidates visible. Automatic restart/resume is not implemented; do not treat an interrupted report as complete.
- The client validates answer IDs, primitives, probability distributions, weighted scores, and token usage. A missing or malformed response fails validation.
- Only explicit HTTP 429/529 failures are retried, with bounded backoff and numeric `Retry-After` handling. A 401/422, exhausted retry budget, or unknown transport outcome remains an error. Request bodies and API keys are omitted from transport errors. Redirects are refused.
- Model confidence is not a biological probability or a p-value. Calibrate any use of it separately on representative tasks; preserve deterministic feasibility and complete candidate review.

Use `prioritize --no-model` to retain the full supplied order without API calls, or `evaluate --dry-run` to validate a request without a key. These are offline operations, not simulated inference.
