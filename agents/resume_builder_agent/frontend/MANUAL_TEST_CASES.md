# Manual Frontend Test Cases

## Template Switching After AI Content

1. Open `/resumes`, create a resume, and confirm the app navigates to `/resume/{generated_id}`.
2. Add an experience entry with role, company, and raw input.
3. Click `Improve with AI`, accept at least one generated bullet, then click `Use selected`.
4. Switch between `Modern` and `Classic`.
5. Confirm the accepted AI bullets remain visible in both previews and are still present after clicking `Save`.

## Mixed-Language Input

1. Enter personal info, education, and experience using mixed-language text, such as English plus Hindi or Spanish.
2. Add raw experience notes containing non-English phrases and punctuation.
3. Generate AI bullets and review whether the UI preserves the original characters without layout overflow.
4. Save, reload the page, and confirm mixed-language content still renders in the form and preview.

## Multi-Step Form Validation

1. Try saving a resume with an empty title and note whether the API validation error is surfaced.
2. In Experience, try clicking `Improve with AI` before entering `role` or enough `raw_input`; confirm the button is disabled or the API returns a clear validation message.
3. In Summary, try clicking `Generate with AI` without a target role; confirm the button stays disabled.
4. In Review, try clicking `Tailor My Resume` without a job description; confirm the button stays disabled.
5. Move forward and backward through all steps and confirm entered values are retained.
