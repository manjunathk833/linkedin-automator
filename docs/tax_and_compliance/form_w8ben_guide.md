# US Form W-8BEN Execution Guide for Indian Remote Contractors

**Target Audience:** Senior SDET / Remote Software Contractor (~6.8 YOE)  
**Jurisdiction:** United States Internal Revenue Service (IRS) Department of the Treasury  
**Purpose:** Certify non-US tax status, claim US-India DTAA Treaty Benefits, and eliminate 30% IRS backup withholding.  
**Governing Treaty:** US-India Double Tax Avoidance Agreement (DTAA), Article 12 & Article 15  
**Submission Destination:** Client Accounts Payable / HR Platform (Deel, Remote.com, Rippling, Carta)  

---

## 1. Why Form W-8BEN is Mandatory

Under US Internal Revenue Code (IRC) Chapters 3 and 4 (FATCA), US payors are required to withhold a statutory **30% tax at source** on payments made to foreign persons for services, **unless** the foreign contractor furnishes a valid Form W-8BEN establishing:
1. That the payee is an individual foreign citizen and tax resident of India.
2. That the income is exempt from US tax under the **US-India Double Tax Avoidance Agreement (DTAA)** because services are performed entirely outside the United States.

$$\text{Withholding without W-8BEN: } 30\% \quad \longrightarrow \quad \mathbf{\text{Withholding with W-8BEN: } 0\%}$$

---

## 2. Line-by-Line Form Completion Instructions

### Part I: Identification of Beneficial Owner

| Form Line | Field Title | Instruction / Value to Enter |
|---|---|---|
| **Line 1** | Name of individual | Enter your **full legal name** exactly as shown on your Indian Passport and PAN Card. |
| **Line 2** | Country of citizenship | **India** |
| **Line 3** | Permanent residence address | Enter your residential address in India (e.g., *#102, 4th Cross, Indiranagar, Bengaluru, Karnataka, 560038, India*). **Do NOT use a P.O. Box or client US address.** |
| **Line 4** | Mailing address | Leave blank if identical to Line 3. |
| **Line 5** | U.S. taxpayer ID (SSN/ITIN) | **Leave blank.** (As a foreign contractor without US residency, you do not have an SSN or ITIN). |
| **Line 6a** | Foreign tax identifying number (FTIN) | **Enter your 10-character Indian PAN Number** (e.g., `ABCDE1234F`). This is **mandatory** for claiming treaty benefits. |
| **Line 7** | Reference number(s) | Optional. Enter your Client Contract ID or leave blank. |
| **Line 8** | Date of birth | Enter in US format: **MM-DD-YYYY** (e.g., `05-18-1995`). |

---

### Part II: Claim of Tax Treaty Benefits (Chapter 3)

| Form Line | Field Title | Value to Enter |
|---|---|---|
| **Line 9** | Tax Treaty Residency Certification | Check the box and enter **India**.  <br>*"I certify that the beneficial owner is a resident of India within the meaning of the income tax treaty between the United States and that country."* |
| **Line 10** | Special rates and conditions | **Article & Paragraph:** `Article 12(2)` (Fees for Included Services) or `Article 15` (Independent Personal Services). <br>**Rate of withholding:** `0%`. <br>**Type of income:** `Independent Personal Services / Automated Software Testing & Quality Engineering Consulting`. <br>**Explanation:** Enter: <br>*"The beneficial owner is a bona fide tax resident of India providing software testing, development, and technical consulting services performed entirely from India. The beneficial owner does not maintain a permanent establishment or fixed base in the United States."* |

---

### Part III: Certification & Signature

1. Check the certification statement confirming that the information provided is true, correct, and complete under penalties of perjury.
2. **Sign Here:** Provide your digital signature (via DocuSign / Adobe Sign / Deel platform) or print, ink-sign, and scan.
3. **Date:** Enter the signing date in US format: **MM-DD-YYYY**.
4. **Capacity in which acting:** Leave blank or enter *"Self"*.

---

## 3. Validity & Renewal Cycle

- **3-Year Rule:** A properly completed Form W-8BEN remains valid starting from the date signed until the end of the **third full calendar year** following the year of signature.
  - *Example:* A form signed on October 15, 2026 remains valid until **December 31, 2029**.
- **Change of Circumstances:** If your tax residency changes or you relocate to the US, you must notify the client within 30 days and submit an updated form (e.g., Form W-9 if transitioning to US residency).
