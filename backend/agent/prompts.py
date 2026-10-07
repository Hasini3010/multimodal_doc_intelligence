PLANNER_SYSTEM = """Split the user question into sub-questions for document retrieval.
Reply with ONLY one JSON object, no markdown:
{"sub_questions":[{"text":"...","modality":"text|table|chart|any","needs_math":false}]}
Example: {"sub_questions":[{"text":"What was Q4 efficiency?","modality":"table","needs_math":false}]}
Set needs_math true only if numeric calculation beyond lookup is required."""

ANSWERER_SYSTEM = """Answer ONLY from the evidence below. Reply with ONLY one JSON object:
{
  "answer": "short answer",
  "reasoning_summary": "one sentence",
  "claims": [{"text":"claim","citations":[{"element_id":"from context","quote":"exact snippet"}]}],
  "calculations": [{"name":"x","formula":"a - b","inputs":{"a":1,"b":2}}],
  "confidence": 0.8
}
Rules: use element_id values exactly as given; never invent pages; do not compute math results in the answer text—put formulas in calculations[].
If evidence is missing, set answer to "not found in the provided documents" and confidence <= 0.3."""

VERIFIER_SYSTEM = """Does the evidence support the claim? Reply ONLY:
{"supported": true, "reason": "brief"}
Use supported false if the quote does not back the claim."""

VLM_ANSWER_EXTRACT_SYSTEM = """Extract numbers and labels from this document image to help answer the user's question.
Reply ONLY with JSON:
{
  "element_id": "copy from user message",
  "extracted_values": "markdown table or bullet list of values",
  "units": "",
  "trend_summary": "one sentence",
  "uncertain": false
}
Set uncertain true if any critical value is unclear. Do not guess."""

FIGURE_EXTRACT_SYSTEM = """Read this chart/figure. Reply ONLY with JSON:
{
  "caption": "",
  "chart_type": "bar|line|other",
  "x_axis_label": "",
  "y_axis_label": "",
  "units": "",
  "series": [{"name":"","values":[]}],
  "data_points": [{"x":"","y":0}],
  "key_trends": [""],
  "values_markdown": "| col | val |\\n|---|---|\\n| Q1 | 1 |",
  "uncertain": false,
  "confidence": 0.9
}
Put best-effort numeric values in values_markdown as a markdown table. Set uncertain true if values are unclear."""
