---
name: visualization_reliability
priority: 10
description: Visualization planning reliability guidelines for empty tables, retries, and large datasets.
---

# Visualization Reliability Guidelines

## Data Awareness

Before proposing charts, consider:
- Check table row counts from the provided schema
- Verify table/column names exist in the schema
- If target tables are empty, consider diagnostic charts instead of hypothesis-specific visualizations

## Empty Table Handling

If key tables are empty (0 rows):
- Consider proposing a diagnostic chart first (e.g., table row count bar chart)
- Acknowledge data limitations in your analysis
- Focus on what data IS available rather than what isn't

## Chart Description Quality

- Provide a concrete `tool_description` that can be executed directly
- Reference actual table/column names from the schema
- If previous attempt failed, revise based on feedback

## Large Dataset Considerations

- For tables with > 50,000 rows, consider sampling strategies
- Prefer aggregation over raw data visualization for large datasets
- Use appropriate chart types for data volume

## Iteration & Feedback

The system compresses iteration history into summaries. Focus on:
- Key findings from previous attempts
- What worked and what didn't
- Recommended next steps
