# AI Trusted Execution Tracker

As of: 2026-05-21

This is research decision support, not investment advice. The operating thesis is
that the scarce asset is trusted execution of intelligence: authority, action,
verification, liability, and the human attention needed to supervise them.

## Control-Layer Dashboard

| control_layer   |   indicator_score | prediction_score   |   indicator_count |   prediction_count |
|:----------------|------------------:|:-------------------|------------------:|-------------------:|
| authority       |              33.9 | 45.0               |                 3 |                  1 |
| capacity        |              65   | 68.2               |                 3 |                  1 |
| cost            |              69.9 | 55.0               |                 4 |                  1 |
| meta            |              51.2 | 50.5               |                 2 |                  1 |
| outcome         |              30.4 | 48.2               |                 2 |                  1 |
| watchlist       |              45   | n/a                |                 1 |                  0 |

## Portfolio Control-Rights Exposure

Exposures can overlap by design; this table is a control-rights map, not a sum-to-100 allocation.

| control_layer   | exposure_weight   | top_holdings                                                                 |
|:----------------|:------------------|:-----------------------------------------------------------------------------|
| capacity        | 42.0%             | 000660.KS 8.0%; NVDA 7.0%; TSM 7.0%; AVGO 5.0%; CEG 5.0%; TER 5.0%; VRT 5.0% |
| authority       | 33.0%             | MSFT 18.0%; GOOGL 15.0%                                                      |
| outcome         | 26.0%             | MSFT 10.0%; GOOGL 8.0%; MCO 2.0%; MSCI 2.0%; SPGI 2.0%; VEEV 2.0%            |
| cost            | 18.0%             | GOOGL 8.0%; AVGO 5.0%; NVDA 5.0%                                             |
| risk_control    | 10.0%             | CASH 10.0%                                                                   |
| physical_ai     | 2.0%              | TER 2.0%                                                                     |

## Leading Indicators

| control_layer   | indicator_name                                         | current_value   | target_value   | warning_value   | unit              | computed_status   |   indicator_score | confidence   | notes                                                                                                    |
|:----------------|:-------------------------------------------------------|:----------------|:---------------|:----------------|:------------------|:------------------|------------------:|:-------------|:---------------------------------------------------------------------------------------------------------|
| authority       | Enterprise agent control-plane penetration             | n/a             | 20             | 5               | pct               | unknown           |                45 | 25%          | Track Agent 365 and equivalent authority layer deployments                                               |
| authority       | Expert review minutes per verified task                | 20              | 5              | 15              | minutes           | red               |                20 | 40%          | Human attention bottleneck remains binding until routed review minutes fall                              |
| authority       | Agents with production write permission                | n/a             | 20             | 5               | pct               | unknown           |                45 | 25%          | Core trust plateau indicator                                                                             |
| capacity        | Advanced packaging tightness                           | n/a             | n/a            | n/a             | utilization_proxy | unknown           |                45 | 25%          | Track TSMC CoWoS expansion lead times pricing and backlog                                                |
| capacity        | HBM4 supplier concentration in Vera Rubin generation   | 5               | 10             | 30              | pct               | green             |                85 | 45%          | Micron share is a thesis seed and must be verified before position sizing                                |
| capacity        | Nodal power scarcity for AI data centers               | n/a             | n/a            | n/a             | scarcity_score    | unknown           |                45 | 25%          | Track nuclear PPAs interconnect queues and hyperscaler site constraints                                  |
| cost            | Hyperscaler custom silicon share of frontier inference | 12.5            | 25             | 15              | pct               | yellow            |                55 | 40%          | Seed uses thesis range for 2025 baseline and needs external verification                                 |
| cost            | Frontier GPU workload volume expansion                 | 75              | 40             | 10              | pct               | green             |                85 | 45%          | User-supplied NVDA data-center growth signal                                                             |
| cost            | AI factory networking growth signal                    | 263             | 50             | 20              | pct               | green             |                85 | 45%          | User-supplied networking growth signal for AI factory buildout                                           |
| cost            | Risk-adjusted cost per verified task                   | n/a             | 90             | 110             | index             | unknown           |                45 | 25%          | Track whether TCAO declines after inference tool latency review integration compliance and failure costs |
| meta            | Linji qualitative capability frontier assessment       | n/a             | 70             | 40              | score             | unknown           |                45 | 25%          | Manual post-paper or post-conference assessment of capability frontier and verification bottlenecks      |
| meta            | METR task-horizon doubling time                        | 89              | 60             | 120             | days              | yellow            |                55 | 40%          | Capability scaling speed from user thesis seed                                                           |
| outcome         | Proprietary verifier data monetization                 | n/a             | 70             | 40              | score             | unknown           |                45 | 25%          | Qualitative score for trusted outcome-label ownership                                                    |
| outcome         | Vertical verifier public-market rerating count         | 0               | 2              | 1               | count             | red               |                20 | 35%          | Track MCO SPGI Veeva IDXX MSCI style reratings                                                           |
| watchlist       | Agent runtime security and observability monetization  | n/a             | 10             | 3               | pct               | unknown           |                45 | 25%          | Track DDOG CRWD PANW OKTA and private agent infra proxies for agent-specific revenue or IPO trigger      |

## Falsifiable Predictions

| control_layer   | prediction_text                                                                 | deadline   | target_threshold   | current_value   | unit   | status   | probability   | falsifier                                                     |
|:----------------|:--------------------------------------------------------------------------------|:-----------|:-------------------|:----------------|:-------|:---------|:--------------|:--------------------------------------------------------------|
| cost            | Hyperscaler internal silicon reaches material frontier inference share          | 2027-06-30 | >=25 pct           | 12.5            | pct    | watch    | 55%           | Share remains below 15 pct by 2027 Q2                         |
| authority       | Enterprise agents with production write permission become common in Fortune 500 | 2027-06-30 | >=20 pct           | n/a             | pct    | unknown  | 45%           | Penetration remains below 5 pct by 2027 mid-year              |
| capacity        | SK Hynix plus Samsung maintain Vera Rubin HBM4 supplier dominance               | 2027-06-30 | <10 pct            | 5               | pct    | on_track | 60%           | Micron reaches 30 pct plus share in Rubin Ultra or Rubin CPX  |
| meta            | METR task-horizon doubling time compresses below 60 days                        | 2027-05-31 | <60 days           | 89              | days   | watch    | 45%           | Doubling time stabilizes at 90 to 120 days                    |
| outcome         | Two or more vertical incumbents rerate as AI winners because of verifier data   | 2027-06-30 | >=2 companies      | 0               | count  | watch    | 40%           | No public-market rerating captured in vertical verifier layer |

## Scenario Weights

| scenario_name                                            | probability   | scenario_type   | thesis_impact                                                                | portfolio_posture                                                    |
|:---------------------------------------------------------|:--------------|:----------------|:-----------------------------------------------------------------------------|:---------------------------------------------------------------------|
| Agent autonomy discontinuity or alignment breakthrough   | 10%           | tail            | Existing authority and verification assumptions can break quickly            | Re-underwrite framework and raise scenario review frequency          |
| AI capex narrative crack or infrastructure bust          | 10%           | tail            | Compresses high-duration AI infrastructure multiples                         | Use cash to add only after evidence stabilizes                       |
| Continued capability scaling with gradual trust buildout | 35%           | base            | Supports integrators and trusted execution layers                            | Maintain core compounders and monitor human-review bottleneck        |
| Hyperscaler custom silicon shifts inference economics    | 15%           | transition      | Pressures GPU margins while benefiting TPU ASIC and networking beneficiaries | Overweight GOOGL AVGO and retain smaller NVDA exposure               |
| Sovereign and geopolitical fragmentation                 | 10%           | tail            | Creates regional access moats and supply-chain discontinuities               | Favor non-technical moats and avoid single-stack assumptions         |
| Trust and liability plateau slows agent write access     | 20%           | risk            | Authority layer adoption disappoints and human review remains binding        | Keep dry powder and favor workflow verifiers over raw model exposure |

## Monitoring Questions

| regime            | question                                                    | current   | unit   | status   | trigger                                                                           |
|:------------------|:------------------------------------------------------------|:----------|:-------|:---------|:----------------------------------------------------------------------------------|
| Capability regime | Does METR task horizon keep extending?                      | 89        | days   | yellow   | If doubling time compresses below 60 days, reassess toward authority/outcome.     |
| Economic regime   | Does risk-adjusted cost per verified task keep declining?   | n/a       | index  | unknown  | If TCAO does not decline, compress pure capacity exposure.                        |
| Trust regime      | Do enterprise agents keep gaining write/execute permission? | n/a       | pct    | unknown  | If Fortune 500 write-permission penetration stalls below 10%, reassess authority. |

## Watchlist Gaps

- Agent runtime security and observability monetization: status=unknown, target=10pct; Track DDOG CRWD PANW OKTA and private agent infra proxies for agent-specific revenue or IPO trigger

## Portfolio Decision System

| ticker    | bucket                   | target_weight   | current_weight   | suggested_weight   |   decision_score | decision_label               | rebalance_flag                       |
|:----------|:-------------------------|:----------------|:-----------------|:-------------------|-----------------:|:-----------------------------|:-------------------------------------|
| 000660.KS | Bottleneck Cyclicals     | 8.0%            | 8.0%             | 8.0%               |             62.9 | Hold target / monitor        | within band                          |
| AVGO      | Core Compounders         | 10.0%           | 10.0%            | 10.0%              |             65.5 | Hold target / monitor        | within band                          |
| CASH      | Dry Powder               | 10.0%           | 10.0%            | 12.0%              |             84.2 | Maintain dry powder          | consider add toward suggested weight |
| CEG       | Bottleneck Cyclicals     | 5.0%            | 5.0%             | 5.0%               |             62.9 | Hold target / monitor        | within band                          |
| GOOGL     | Core Compounders         | 15.0%           | 15.0%            | 15.0%              |             55   | Watch / require new evidence | within band                          |
| MCO       | Vertical Verifier Basket | 2.0%            | 2.0%             | 2.0%               |             45.6 | Watch / require new evidence | within band                          |
| MSCI      | Vertical Verifier Basket | 2.0%            | 2.0%             | 2.0%               |             46.2 | Watch / require new evidence | within band                          |
| MSFT      | Core Compounders         | 18.0%           | 18.0%            | 18.0%              |             46.5 | Watch / require new evidence | within band                          |
| NVDA      | Core Compounders         | 7.0%            | 7.0%             | 7.0%               |             64.9 | Hold target / monitor        | within band                          |
| SPGI      | Vertical Verifier Basket | 2.0%            | 2.0%             | 2.0%               |             45.6 | Watch / require new evidence | within band                          |
| TER       | Asymmetric Optionality   | 7.0%            | 7.0%             | 7.0%               |             63.5 | Hold target / monitor        | within band                          |
| TSM       | Core Compounders         | 7.0%            | 7.0%             | 7.0%               |             66   | Hold target / monitor        | within band                          |
| VEEV      | Vertical Verifier Basket | 2.0%            | 2.0%             | 2.0%               |             45.6 | Watch / require new evidence | within band                          |
| VRT       | Bottleneck Cyclicals     | 5.0%            | 5.0%             | 5.0%               |             63.5 | Hold target / monitor        | within band                          |

## Review Queue

- indicator: authority / Enterprise agent control-plane penetration is unknown
- indicator: authority / Expert review minutes per verified task is red
- indicator: authority / Agents with production write permission is unknown
- indicator: capacity / Advanced packaging tightness is unknown
- indicator: capacity / Nodal power scarcity for AI data centers is unknown
- indicator: cost / Risk-adjusted cost per verified task is unknown
- indicator: meta / Linji qualitative capability frontier assessment is unknown
- indicator: outcome / Proprietary verifier data monetization is unknown
- indicator: outcome / Vertical verifier public-market rerating count is red
- indicator: watchlist / Agent runtime security and observability monetization is unknown
- prediction: pred_enterprise_agent_write_permission status=unknown deadline=2027-06-30
- holding: CASH consider add toward suggested weight (Maintain dry powder)

## Update Loop

1. Update the four CSVs under `data/manual/ai_framework_*.csv`.
2. Run `uv run python -m scripts.import_ai_framework`.
3. Run `uv run python -m scripts.build_ai_framework_tracker`.
4. Review red indicators, at-risk predictions, and any rebalance flags before
   changing weights.
