// Clean, ATS-Compliant Single-Column Resume Template in Typst
#set page(paper: "a4", margin: (x: 1.8cm, y: 1.8cm))
#set text(font: "Helvetica", size: 9.5pt)
#set par(justify: false, leading: 0.55em)

// Header
#align(center)[
  #text(size: 16pt, weight: "bold")[#FULL_NAME] \
  #v(2pt)
  #text(size: 10pt, weight: "medium", fill: rgb("#2563eb"))[#LABEL] \
  #v(2pt)
  #text(size: 8.5pt, fill: rgb("#475569"))[#EMAIL  |  #PHONE  |  #LOCATION]
]

#v(4pt)
#line(length: 100%, stroke: 0.5pt + rgb("#cbd5e1"))

// Summary
#text(size: 11pt, weight: "bold", fill: rgb("#0f172a"))[PROFESSIONAL SUMMARY]
#v(2pt)
#SUMMARY_TEXT

#v(6pt)
// Experience
#text(size: 11pt, weight: "bold", fill: rgb("#0f172a"))[EXPERIENCE]
#v(2pt)
#EXPERIENCE_BLOCKS

#v(6pt)
// Education & Skills
#text(size: 11pt, weight: "bold", fill: rgb("#0f172a"))[CORE TECHNICAL SKILLS]
#v(2pt)
#SKILLS_BLOCK
