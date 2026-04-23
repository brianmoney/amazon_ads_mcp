# Scoring Reference — Weighted Health Score Model

Used by: `amz-sp-audit`, `amz-ads` orchestrator, and all audit agents.

## Health Score Overview

Overall health score is 0–100, composed of four equal-weight dimensions (25 points each):

| Dimension | Weight | Sourced From |
|---|---|---|
| Keyword efficiency | 25 pts | `get_keyword_performance` |
| Search-term hygiene | 25 pts | `get_search_term_report` |
| Bid calibration | 25 pts | `get_keyword_performance` + target ACoS |
| Campaign structure | 25 pts | `list_campaigns` |

## Letter Grades

| Score | Grade | Interpretation |
|---|---|---|
| 90–100 | A | Excellent — minor or no issues |
| 75–89 | B | Good — a few optimization opportunities |
| 60–74 | C | Fair — meaningful issues to address |
| 45–59 | D | Poor — significant inefficiencies |
| 0–44 | F | Critical — immediate action required |

## Dimension Scoring Rules

### Keyword Efficiency (0–25)

Start at 25. Apply deductions:

| Condition | Deduction |
|---|---|
| Pause candidates ≥ 10% of active keywords | −5 |
| Pause candidates ≥ 25% of active keywords | −10 (cumulative with above) |
| Average campaign ACoS > target × 1.5 | −5 |
| Average campaign ACoS > target × 2.0 | −10 (cumulative) |
| Keywords with no impressions > 30% of total | −3 |
| Insufficient data (below min-volume threshold) for > 50% of keywords | −5 |

### Search-Term Hygiene (0–25)

Start at 25. Apply deductions:

| Condition | Deduction |
|---|---|
| Waste terms ≥ 5% of total spend | −5 |
| Waste terms ≥ 15% of total spend | −10 (cumulative) |
| Harvest candidates not yet targeted ≥ 5 | −3 |
| Harvest candidates not yet targeted ≥ 20 | −6 (cumulative) |
| Auto campaign with zero negatives | −4 per campaign, max −8 |

### Bid Calibration (0–25)

Start at 25. Apply deductions:

| Condition | Deduction |
|---|---|
| Keywords with ACoS > target × 1.5 AND sufficient data | −2 each, max −10 |
| Keywords with zero spend for > 30 days | −2 each, max −8 |
| No keywords eligible for bid adjustment (all insufficient data) | −5 |

### Campaign Structure (0–25)

Start at 25. Apply deductions:

| Condition | Deduction |
|---|---|
| No auto research campaign in account | −8 |
| No exact performance campaign | −5 |
| Mixed match types in same ad group | −3 per ad group, max −9 |
| Auto campaign with no negatives | −4 per campaign, max −8 |

## Severity Multipliers

Apply severity multipliers when computing final narrative (do not adjust raw score — use for priority sorting):

| Severity | Multiplier | Use When |
|---|---|---|
| Critical | 2.0× | Gate blocked AND condition affects > 50% of spend |
| High | 1.5× | Gate blocked OR ACoS > 2× target |
| Medium | 1.0× | Standard Quality Gate violation |
| Low | 0.5× | Advisory finding, insufficient data, or unsupported analysis |

## Data Confidence Penalty

If fewer than 30% of keywords meet the minimum-volume threshold for the reporting window, add a confidence penalty note to the overall score:

> **Confidence: Limited** — fewer than 30% of keywords have sufficient data. Health score may understate account efficiency. Extend the reporting window to improve signal quality.

Do not reduce the numeric score for confidence — only add the note.

## Score Section Citation Format

Every score section must include:

```
Keyword Efficiency: 18/25
  Sources: get_keyword_performance (YYYY-MM-DD to YYYY-MM-DD)
  Deductions: -5 (pause candidates ≥ 25%), -2 (average ACoS 1.6× target)
  Gates passed: min_clicks_threshold, attribution_window_14d
  Gates blocked: none
```
