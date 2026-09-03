# CLAUDE.md

Projeto CBL Spotify — separa **entrega** (`entregas/`, notebooks) de **produto** (`produto/`, MVP),
com a documentação de decisões em `docs/`.

## Agent skills

### Issue tracker

Issues ficam no GitHub (`feliperodri0/spotify-mood-playlist`), operadas pela CLI `gh`. See `docs/agents/issue-tracker.md`.

### Triage labels

Vocabulário canônico padrão: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

single-context — um `CONTEXT.md` na raiz e ADRs em `docs/adr/`. See `docs/agents/domain.md`.
