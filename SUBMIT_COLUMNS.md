# Submit Excel columns

## Subject input modes

The Submit screen supports two Class 11 subject workflows. **Subject Names is the default and recommended mode.**

### 1. Subject Names (default)
Use `sub1`, `sub2`, `sub3`, ... (or `Subjects`) and enter visible names such as `General English`, `Physics`, `Biology`, `Mathematics`, `Physical Education`, `IT and ITES`. The tool selects the Stream first, reads the live JKBOSE subject grid, matches optional subjects by label, and routes recognized vocational names to the vocational dropdown. Numeric subject codes are not required.

Recommended Class 11 columns:
`RegNo, Class, Stream, Gender, Religion, Category, Email, Mobile, AddressLine1, AddressLine2, Village/Town, Pincode, District, Area, PermanentSameCurrent, Disability, DisabilityPercent, sub1, sub2, sub3, sub4, sub5, sub6, sub7, AdditionalSubject, PhotoPath, SignaturePath, pho, sig, Status, Notes`

### 2. Subject Codes (legacy)
Choose **Subject Codes (legacy)** in the Submit screen. Keep the older numeric fields such as `Group2_choice` through `Group8_choice`; `SubjectCode1`, `SubjectCode2`, ... are also accepted. The value must be the JKBOSE radio `value`, not an element id. `VocationalCode` continues to select the vocational dropdown by numeric code.

Recommended legacy/code columns:
`RegNo, Class, Stream, ... , VocationalCode, Group2_choice, Group3_choice, Group4_choice, Group5_choice, Group6_choice, Group7_choice, Group8_choice, AdditionalSubject, PhotoPath, SignaturePath, pho, sig, Status, Notes`

The software bundles a separate Class 11 template for each mode. The **Download Class 11 Template** button automatically downloads the template matching the currently selected Subject Input Mode.

## Class 12 renewal
Normally only these columns are needed:
`RegNo, Class, Status, Notes`

Class 12 stream/subjects/photo/signature are not changed in the normal renewal workflow.
