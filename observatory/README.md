# Harness Observatory

Engineering intelligence dashboard for repos running the native harness. Tracks harness adoption, AI commit percentage, commit size, rework rate, and benchmark results.

## Setup

```bash
cp repos.yaml.example repos.yaml
cp mailmap.yaml.example mailmap.yaml
# Edit both files for your repos and team
```

Set your GitHub token:
```bash
export GITHUB_TOKEN=ghp_...
```

## Run

```bash
npm install
npm run dev
```

Open http://localhost:5173

## Config files

| File | Purpose | Committed? |
|---|---|---|
| `repos.yaml` | Your repos + local paths | No — gitignored |
| `repos.yaml.example` | Template | Yes |
| `mailmap.yaml` | Author alias resolution | No — gitignored |
| `mailmap.yaml.example` | Template | Yes |
| `benchmarks.yaml` | Metric thresholds | Yes |
