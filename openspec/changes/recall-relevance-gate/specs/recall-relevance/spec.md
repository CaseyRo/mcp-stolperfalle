## Purpose

Keeps error-driven recall from injecting knowledge units that do not apply to the error, by asking Jev per candidate whether it applies before `/hook/query` returns it.

## ADDED Requirements

### Requirement: Hook query results are gated on relevance
When a relevance key is configured, `/hook/query` SHALL retrieve a shortlist of candidates by the existing ranking, ask Jev for each whether it applies to the query text, and return in `results` only candidates whose answer is in the ACT band, highest probability first, up to the requested limit.

#### Scenario: ACT band
- **WHEN** a candidate is judged to apply with a probability in the ACT band
- **THEN** it is included in `results`

#### Scenario: CONFIRM band
- **WHEN** a candidate's probability is in the CONFIRM band
- **THEN** it is returned under `hints`, not in `results`

#### Scenario: ASK band
- **WHEN** a candidate's probability is below the CONFIRM band
- **THEN** it is returned in neither `results` nor `hints`

#### Scenario: Nothing applies
- **WHEN** no candidate reaches the ACT band
- **THEN** `results` is empty and `count` is 0, even though the ranker found matches

### Requirement: Unavailability degrades to today's behaviour
When no relevance key is configured, or the Jev call fails or times out, `/hook/query` SHALL return exactly the results it returns today and SHALL set `degraded: true` in the response. It SHALL NOT return an error because of the relevance step.

#### Scenario: Key unset
- **WHEN** the server has no relevance key
- **THEN** the response carries today's ranked results and `degraded: true`

#### Scenario: Jev times out
- **WHEN** the relevance call fails or exceeds its timeout
- **THEN** the response carries today's ranked results and `degraded: true` with status 200

### Requirement: The MCP query tool is unaffected
The `query` MCP tool SHALL NOT apply the relevance gate.

#### Scenario: Agent queries deliberately
- **WHEN** an agent calls the `query` tool with a key configured
- **THEN** it receives the full ranked list as before
