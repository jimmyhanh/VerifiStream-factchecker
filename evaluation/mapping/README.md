# Mapping semantic smoke cases

Twelve **authored synthetic** examples cover five relationships, abstention, causation,
dates, percent vs points, prediction and injected instructions. Labels are provisional
rubric examples for human review, not independently adjudicated ground truth. These
are not held out and must not be presented as real-world accuracy.

`backend/tests/test_mapping.py` tests contracts with stub responses; it does not test
LLM semantic quality or prove prompt-injection resistance.

To run the optional paid model check from the repository root, install the backend,
export OPENAI_API_KEY and MAPPING_MODEL into the process, then run:

```bash
python evaluation/mapping/evaluate.py --live --output mapping-eval-2026-10-18.json
```

The script does not load .env automatically. It stores inputs, decisions, prompt,
model, usage and exact-quote checks. Choose a fresh output name. Review explanations
and quotations manually, particularly attribution, time scope and causal reasoning.
Before claiming model accuracy, expand to independently labeled realistic passages,
reserve a held-out set, and report per-class precision/recall, abstention coverage,
citation correctness, latency and token usage. No live result is recorded yet.
