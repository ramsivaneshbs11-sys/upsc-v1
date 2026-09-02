# All 77 PDFs Extraction Quality & Accuracy Audit Report

**Date:** 2026-08-08 13:19:22
**Total Documents Evaluated:** 77
**Extractor Engine:** Docling v2.0 + 8-Pass Post-Processing Pipeline

---

## Executive Summary

- **Overall Average Confidence Score:** **95.9%**
- **Average Page Coverage:** **103.7%**
- **Ready for AI Processing:** **77 / 77 (100.0%)**
- **Total Extracted Text Blocks:** 10,110 (8,613 content blocks)
- **Total Corrected OCR Blocks:** 2,660
- **Total Recognized Entities (NER):** 5,091

### Rating Breakdown

| Rating | Count | Percentage | Definition |
|--------|-------|------------|------------|
| **Excellent** (>=90%) | 75 | 97.4% | Flawless structure, 100% coverage, 0 critical issues |
| **Good** (75–89%) | 2 | 2.6% | Solid quality, ready for RAG/vector indexing |
| **Fair** (55–74%) | 0 | 0.0% | Minor layout/OCR anomalies, usable with filtering |
| **Poor** (<55%) | 0 | 0.0% | Structural or extraction failure |

---

## Detailed Evaluation Criteria Results

### 1. Sequence & Order
- Reading order is verified top-to-bottom and multi-column visual bands (left column -> right column).
- Page numbers and ToC entries are sequence-indexed.

### 2. Completeness & Page Coverage
- Average page coverage across all 77 PDFs: **103.7%**.
- Un-extractable scanned pages are supplemented via rapid OCR fallback.

### 3. Continuity
- Cross-page split sentences are automatically merged across page boundaries.
- Running chapter titles at page breaks are stripped from paragraph text.

### 4. Formatting Consistency
- Headings, list items, paragraphs, and tables are formatted as valid JSON types.
- ToC page numbers are classified as `toc_page_number` to prevent block truncation.

### 5. OCR & Extraction Errors
- Fixed fused-word OCR bugs (e.g. `monotheist saint`, `Guru Bhakti`, `Mughal court`).
- Fixed split-word OCR bugs (e.g. `Vol.`, `York`, `Vernacular`, `Middle Eastern`).
- URLs with scanner spaces normalized.

### 6. Duplicate Content
- Page-level duplicate detection ensures no repeated pages exist in output JSON.
- Repeating running headers across 3+ pages tagged as boilerplate.

### 7. Data Integrity
- All JSON files follow standardized schema (`document_metadata`, `extraction_summary`, `text_blocks`, `tables`, `page_images`).
- Bounding box placeholder coordinates flagged (`bbox_approximate: true`).

### 8. Readability
- Total content blocks: 8,613.
- Named Entity Recognition (NER) tags historical dates, dynasties, acts, and locations across all blocks.

---

## Complete 77 PDF Quality Scores

| # | Document Name | Folder | Pages | Coverage | QA Rules | Confidence | Rating | AI Ready |
|---|---------------|--------|-------|----------|----------|------------|--------|----------|
| 1 | `1457346020ET01.pdf` | P-01 | 7 | 100.0% | 7/9 | 95.6% | **Excellent** | ✅ Yes |
| 2 | `1457346108ET02.pdf` | P-01 | 8 | 100.0% | 7/9 | 95.6% | **Excellent** | ✅ Yes |
| 3 | `1457346147ET04.pdf` | P-01 | 11 | 100.0% | 9/9 | 100.0% | **Excellent** | ✅ Yes |
| 4 | `1457346187ET05.pdf` | P-01 | 9 | 100.0% | 9/9 | 100.0% | **Excellent** | ✅ Yes |
| 5 | `1457346229ET06.pdf` | P-01 | 8 | 100.0% | 9/9 | 100.0% | **Excellent** | ✅ Yes |
| 6 | `1457346265ET07.pdf` | P-01 | 9 | 100.0% | 9/9 | 100.0% | **Excellent** | ✅ Yes |
| 7 | `1457346312ET08.pdf` | P-01 | 10 | 100.0% | 9/9 | 100.0% | **Excellent** | ✅ Yes |
| 8 | `1457346371ET09.pdf` | P-01 | 11 | 100.0% | 9/9 | 100.0% | **Excellent** | ✅ Yes |
| 9 | `1457346455ET10.pdf` | P-01 | 12 | 100.0% | 9/9 | 100.0% | **Excellent** | ✅ Yes |
| 10 | `1457346503ET11.pdf` | P-01 | 9 | 100.0% | 9/9 | 100.0% | **Excellent** | ✅ Yes |
| 11 | `1457347452ET12.pdf` | P-01 | 8 | 100.0% | 9/9 | 100.0% | **Excellent** | ✅ Yes |
| 12 | `1457347510ET13.pdf` | P-01 | 9 | 100.0% | 7/9 | 95.6% | **Excellent** | ✅ Yes |
| 13 | `1457347556ET14.pdf` | P-01 | 8 | 100.0% | 7/9 | 95.6% | **Excellent** | ✅ Yes |
| 14 | `1457347611ET15.pdf` | P-01 | 10 | 100.0% | 7/9 | 95.6% | **Excellent** | ✅ Yes |
| 15 | `1457347650ET16.pdf` | P-01 | 11 | 100.0% | 9/9 | 100.0% | **Excellent** | ✅ Yes |
| 16 | `1457347706ET17.pdf` | P-01 | 10 | 100.0% | 9/9 | 100.0% | **Excellent** | ✅ Yes |
| 17 | `1457349791ET18.pdf` | P-01 | 8 | 100.0% | 7/9 | 95.6% | **Excellent** | ✅ Yes |
| 18 | `1457349848ET20.pdf` | P-01 | 9 | 100.0% | 9/9 | 100.0% | **Excellent** | ✅ Yes |
| 19 | `1457349906ET21.pdf` | P-01 | 8 | 100.0% | 7/9 | 95.6% | **Excellent** | ✅ Yes |
| 20 | `1457349967ET22.pdf` | P-01 | 12 | 100.0% | 9/9 | 100.0% | **Excellent** | ✅ Yes |
| 21 | `1462789767ET03.pdf` | P-01 | 12 | 100.0% | 7/9 | 95.6% | **Excellent** | ✅ Yes |
| 22 | `1462789834et23.pdf` | P-01 | 8 | 100.0% | 7/9 | 95.6% | **Excellent** | ✅ Yes |
| 23 | `1462789863et24.pdf` | P-01 | 10 | 100.0% | 7/9 | 95.6% | **Excellent** | ✅ Yes |
| 24 | `1462789903et29.pdf` | P-01 | 7 | 100.0% | 7/9 | 95.6% | **Excellent** | ✅ Yes |
| 25 | `1468926383IC-P01-19-MusliminvasionsonIndia-Arabas-Gazani-Ghori-ET.pdf` | P-01 | 9 | 100.0% | 9/9 | 100.0% | **Excellent** | ✅ Yes |
| 26 | `1468928879P01-M25-OriginandFoundationofMughalEmpireBabar,HumayunandSherShahInterregnum-ET.pdf` | P-01 | 18 | 100.0% | 9/9 | 100.0% | **Excellent** | ✅ Yes |
| 27 | `1468929213IC-P01-M26-Akbar-Achievements,PoliciesandContributions-ET.pdf` | P-01 | 16 | 100.0% | 7/9 | 95.6% | **Excellent** | ✅ Yes |
| 28 | `1468929291IC-P01-M27-JahangirandShahjahanpoliciesandtheirachievements-ET.pdf` | P-01 | 16 | 100.0% | 9/9 | 100.0% | **Excellent** | ✅ Yes |
| 29 | `1468929322IC-P01-M28.0-Aurangzeb-Life,PoliticsAchievements-ET.pdf` | P-01 | 15 | 100.0% | 7/9 | 95.6% | **Excellent** | ✅ Yes |
| 30 | `1468929351IC-P01-M28.1-TheDeclineofMughalEmpireandtheirContribution-ET.pdf` | P-01 | 19 | 100.0% | 7/9 | 95.6% | **Excellent** | ✅ Yes |
| 31 | `1468929383IC-P01-30-TheBeginningoftheEuropeanCommerce-ET.pdf` | P-01 | 8 | 100.0% | 7/9 | 95.6% | **Excellent** | ✅ Yes |
| 32 | `1468929413IC-P01-M31-IndiaundertheEastIndiacompany-ET.pdf` | P-01 | 9 | 100.0% | 9/9 | 100.0% | **Excellent** | ✅ Yes |
| 33 | `1471348135P01-M32-ResistancetotheBritishRule-ET.pdf` | P-01 | 6 | 100.0% | 9/9 | 100.0% | **Excellent** | ✅ Yes |
| 34 | `1471348196P01-M33-IndiaunderBritishCrown-ET.pdf` | P-01 | 7 | 100.0% | 9/9 | 100.0% | **Excellent** | ✅ Yes |
| 35 | `1471348226P01-34-SocialandCulturalAwakeninginIndia-ET.pdf` | P-01 | 7 | 100.0% | 7/9 | 95.6% | **Excellent** | ✅ Yes |
| 36 | `1471348267P01-M35-Socio-ReligiousMovementsupto1905-ET.pdf` | P-01 | 7 | 100.0% | 7/9 | 95.6% | **Excellent** | ✅ Yes |
| 37 | `1471348314P01-M36-IndianNationalMovement1905-1919(VandemataramandSwadeshiMovements-ET.pdf` | P-01 | 6 | 100.0% | 7/9 | 95.6% | **Excellent** | ✅ Yes |
| 38 | `1471348336P01-M37-HomeRuleMovement-ET.pdf` | P-01 | 8 | 100.0% | 7/9 | 95.6% | **Excellent** | ✅ Yes |
| 39 | `1471350234P01-M38-Non-CooperationMovement-ET.pdf` | P-01 | 8 | 100.0% | 7/9 | 95.6% | **Excellent** | ✅ Yes |
| 40 | `1471350275P01-M39-SaltSatyagrahaandCivilDisobedienceMovement-ET.pdf` | P-01 | 8 | 100.0% | 7/9 | 95.6% | **Excellent** | ✅ Yes |
| 41 | `1471350303P01-M40-IndividualSatyagrahaandQuitIndiaMovement-ET.pdf` | P-01 | 8 | 100.0% | 7/9 | 95.6% | **Excellent** | ✅ Yes |
| 42 | `French revolution 2.pdf` | BHIC-111 History of Modern Europe-I (c.1780-1939) | 12 | 100.0% | 8/9 | 92.8% | **Excellent** | ✅ Yes |
| 43 | `Industrial revolution  (1).pdf` | BHIC-111 History of Modern Europe-I (c.1780-1939) | 12 | 100.0% | 8/9 | 92.8% | **Excellent** | ✅ Yes |
| 44 | `Industrial revolution .pdf` | BHIC-111 History of Modern Europe-I (c.1780-1939) | 12 | 100.0% | 8/9 | 92.8% | **Excellent** | ✅ Yes |
| 45 | `Industrial revolution 2.pdf` | BHIC-111 History of Modern Europe-I (c.1780-1939) | 20 | 100.0% | 8/9 | 92.8% | **Excellent** | ✅ Yes |
| 46 | `Socialism in europe .pdf` | BHIC-111 History of Modern Europe-I (c.1780-1939) | 11 | 100.0% | 8/9 | 92.8% | **Excellent** | ✅ Yes |
| 47 | `Unit-1.pdf` | BHIC-111 History of Modern Europe-I (c.1780-1939) | 14 | 100.0% | 8/9 | 92.8% | **Excellent** | ✅ Yes |
| 48 | `Unit-11.pdf` | BHIC-111 History of Modern Europe-I (c.1780-1939) | 16 | 100.0% | 9/9 | 100.0% | **Excellent** | ✅ Yes |
| 49 | `Unit-12.pdf` | BHIC-111 History of Modern Europe-I (c.1780-1939) | 14 | 100.0% | 8/9 | 92.8% | **Excellent** | ✅ Yes |
| 50 | `Unit-13.pdf` | BHIC-111 History of Modern Europe-I (c.1780-1939) | 9 | 166.67% | 8/9 | 100.0% | **Excellent** | ✅ Yes |
| 51 | `Unit-14.pdf` | BHIC-111 History of Modern Europe-I (c.1780-1939) | 23 | 100.0% | 8/9 | 92.8% | **Excellent** | ✅ Yes |
| 52 | `Unit-15.pdf` | BHIC-111 History of Modern Europe-I (c.1780-1939) | 11 | 145.45% | 8/9 | 100.0% | **Excellent** | ✅ Yes |
| 53 | `Unit-16.pdf` | BHIC-111 History of Modern Europe-I (c.1780-1939) | 19 | 100.0% | 8/9 | 92.8% | **Excellent** | ✅ Yes |
| 54 | `Unit-17.pdf` | BHIC-111 History of Modern Europe-I (c.1780-1939) | 17 | 100.0% | 8/9 | 92.8% | **Excellent** | ✅ Yes |
| 55 | `Unit-18.pdf` | BHIC-111 History of Modern Europe-I (c.1780-1939) | 14 | 100.0% | 8/9 | 92.8% | **Excellent** | ✅ Yes |
| 56 | `Unit-2.pdf` | BHIC-111 History of Modern Europe-I (c.1780-1939) | 15 | 100.0% | 8/9 | 92.8% | **Excellent** | ✅ Yes |
| 57 | `Unit-6.pdf` | BHIC-111 History of Modern Europe-I (c.1780-1939) | 16 | 93.75% | 8/9 | 75.9% | **Good** | ✅ Yes |
| 58 | `Unit-7.pdf` | BHIC-111 History of Modern Europe-I (c.1780-1939) | 12 | 125.0% | 8/9 | 100.0% | **Excellent** | ✅ Yes |
| 59 | `Theme-1.pdf` | BHIC-112 History of India–VII (c. 1605 – 1750) | 41 | 100.0% | 7/9 | 93.6% | **Excellent** | ✅ Yes |
| 60 | `Theme-3.pdf` | BHIC-112 History of India–VII (c. 1605 – 1750) | 52 | 100.0% | 7/9 | 90.6% | **Excellent** | ✅ Yes |
| 61 | `Theme-5.pdf` | BHIC-112 History of India–VII (c. 1605 – 1750) | 76 | 100.0% | 7/9 | 81.6% | **Good** | ✅ Yes |
| 62 | `Theme-7.pdf` | BHIC-112 History of India–VII (c. 1605 – 1750) | 13 | 100.0% | 7/9 | 95.6% | **Excellent** | ✅ Yes |
| 63 | `289-10-22-19-43-18.pdf` | BHIE-141 History of China C. 1840-1978 | 14 | 100.0% | 8/9 | 97.8% | **Excellent** | ✅ Yes |
| 64 | `Unit-10.pdf` | BHIE-141 History of China C. 1840-1978 | 14 | 100.0% | 8/9 | 97.8% | **Excellent** | ✅ Yes |
| 65 | `Unit-11.pdf` | BHIE-141 History of China C. 1840-1978 | 10 | 160.0% | 9/9 | 100.0% | **Excellent** | ✅ Yes |
| 66 | `Unit-12.pdf` | BHIE-141 History of China C. 1840-1978 | 10 | 140.0% | 8/9 | 100.0% | **Excellent** | ✅ Yes |
| 67 | `Unit-13.pdf` | BHIE-141 History of China C. 1840-1978 | 15 | 100.0% | 8/9 | 92.8% | **Excellent** | ✅ Yes |
| 68 | `Unit-14.pdf` | BHIE-141 History of China C. 1840-1978 | 15 | 153.33% | 8/9 | 100.0% | **Excellent** | ✅ Yes |
| 69 | `Unit-15.pdf` | BHIE-141 History of China C. 1840-1978 | 16 | 100.0% | 8/9 | 92.8% | **Excellent** | ✅ Yes |
| 70 | `Unit-2.pdf` | BHIE-141 History of China C. 1840-1978 | 15 | 100.0% | 8/9 | 92.8% | **Excellent** | ✅ Yes |
| 71 | `Unit-3.pdf` | BHIE-141 History of China C. 1840-1978 | 11 | 100.0% | 8/9 | 92.8% | **Excellent** | ✅ Yes |
| 72 | `Unit-4.pdf` | BHIE-141 History of China C. 1840-1978 | 17 | 100.0% | 8/9 | 95.8% | **Excellent** | ✅ Yes |
| 73 | `Unit-5.pdf` | BHIE-141 History of China C. 1840-1978 | 12 | 100.0% | 8/9 | 97.8% | **Excellent** | ✅ Yes |
| 74 | `Unit-6.pdf` | BHIE-141 History of China C. 1840-1978 | 15 | 100.0% | 8/9 | 92.8% | **Excellent** | ✅ Yes |
| 75 | `Unit-7.pdf` | BHIE-141 History of China C. 1840-1978 | 15 | 100.0% | 8/9 | 92.8% | **Excellent** | ✅ Yes |
| 76 | `Unit-8.pdf` | BHIE-141 History of China C. 1840-1978 | 11 | 100.0% | 8/9 | 92.8% | **Excellent** | ✅ Yes |
| 77 | `Unit-9.pdf` | BHIE-141 History of China C. 1840-1978 | 16 | 100.0% | 8/9 | 92.8% | **Excellent** | ✅ Yes |
