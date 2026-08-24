# Local RAG System Verification Report

**Date/Time:** 2026-08-22 13:21:51
**Ingested Document:** 145793840413ET.pdf

## Test Case Execution Summary

| ID | Scenario | Query | Classification | Confidence | Routing | Answered | Citations | Status | Notes |
|---|---|---|---|---|---|---|---|---|---|
| TC001 | Simple Factual (In-Domain) | Who is the principal investigator for Indian Anthropology Module 13? | Anthropology | 0.64 | medium_confidence | False | 0 | **FAIL** | Expected answer to mention Anup Kumar Kapoor. |
| TC002 | Detailed Concept (In-Domain) | Explain the importance of village studies in Indian anthropology. | Anthropology | 0.99 | high_confidence | True | 4 | **PASS** | No issues |
| TC003 | Out-of-Domain / Low Confidence | How does quantum computing work? | History | 0.10 | low_confidence | False | 0 | **PASS** | No issues |

## Detailed Logs & Trace
All endpoints responded and the local ingestion pipeline was executed fully.
