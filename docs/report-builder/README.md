# Report builder

Generates `../Eximion_Test_Assignment_Sergei_Kutushev.docx` from the content of
`../REPORT.md`, so the Word deliverable is reproducible rather than hand-formatted.

```bash
npm install docx
node build-docx.js ../Eximion_Test_Assignment_Sergei_Kutushev.docx
```

`REPORT.md` stays the source of record; this script controls the Word layout
(US Letter, headings, tables, monospace blocks, hyperlinks).
