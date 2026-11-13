# Local party-language screening

The model reads every source-audited matched listing's full description and amenities, split into bounded chunks. Call counts, addresses, occupancy and outcomes are not model inputs. Reviews, host metadata and duplicate scraped page sections are excluded. Source SHA256 and match-audit hashes are checked. No listing text is sent to an external inference service; pretrained weights are downloaded once, and inference runs locally.

Four independent contextual hypotheses identify explicit party invitations, social/leisure amenities, prohibitions and nearby nightlife. A no-parties rule is not an invitation. Leisure amenities do not imply permission to party. Party/social signals exclude chunks classified as restrictions or nearby nightlife. Mixed claims may therefore be missed; exact excerpts and raw scores are retained for review. A maximum chunk score is a screening signal, not a calibrated probability or a measure of actual guest behavior; longer descriptions have more chances to score highly. Word and chunk counts are exported for this reason.

This is a pretrained zero-shot text classifier, not a model trained to predict police calls. Calls are joined only after text scoring. Failed generic/no-party/invitation sanity checks stop the run. Saved sanity checks do not replace a hand-labelled validation set. Review high and low excerpts before interpreting downstream comparisons. Scores and thresholds are exploratory; police calls do not establish guest responsibility or confirmed offences.

All properties, including zero-call properties and listings without party signals, stay in the result. For residential-average subtraction, each property contributes observed calls minus expected calls; a zero-call property contributes a negative expected count. The dashboard also compares rates with and without a detected signal to avoid rewarding universal features. Neither adjustment establishes causality or removes capacity/location confounding. Neighborhoods can overlap.

Start or resume hidden from the project root with `.\party_sentiment\start_analysis.ps1`. It checks whether our worker is already running. For a foreground run:

```powershell
.\.venv-party\Scripts\python.exe -m processing.party_sentiment
```

`status.json` records PID, progress and failures; `run.stdout.log` and `run.stderr.log` capture background output. Each completed listing is checkpointed to `listing_results.jsonl`. Chunk scores are cached in SQLite. A model/hypothesis/source change invalidates old results automatically. `run_config.json` records the exact downloaded model revision and software version. To stop, stop the PID from status.json after verifying its command line. To resume, run the same command. The dashboard refreshes local result scripts every 30 seconds and preserves its filters.

The fixed residential references include all 4,806 eligible parcels, including zeros, in the covered study footprint. They are not a citywide census. All-citizen and noise/party/disturbance references are different outcomes. Use the same outcome for a comparable reference. The 59% rental scenario affects only focal rental exposure. Missing later parking coverage is not treated as zero. Only retained citizen calls with patrol/proactive exclusions are analyzed.

Model documentation: https://huggingface.co/MoritzLaurer/deberta-v3-base-zeroshot-v1.1-all-33
PyTorch installation: https://pytorch.org/get-started/locally/

The event-marketing signal has an additional conservative text gate: the same sentence must contain an event term and affirmative marketing language. Travel-group homonyms such as "your party" cannot establish the event claim. Synthetic travel-group and catering examples test this gate. Raw classifier scores are still exported separately. This gate can miss subtle invitations and does not prove that an event is permitted; all high signals need review.
