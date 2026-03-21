---
name: xml_contract
priority: 0
description: Strict XML output contract for analysis, judgment, and report generation.
required: true
---

# XML Output Contract (Strict)

- Return only XML requested by the prompt; do not output JSON.
- Do not include prose outside XML tags.
- If the prompt asks for `<report>`, include **bilingual** outputs (four CDATA blocks):
  - `<markdown_zh>`, `<html_zh>` (简体中文)
  - `<markdown_en>`, `<html_en>` (English)
- If one part is hard to produce, still return non-empty placeholders in all four tags.
- Keep tags stable and parsable; avoid changing tag names.
