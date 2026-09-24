import { createInitialResumeBuilderState, handleResumeBuilderText, importResumeBuilderFile, parseEducationInput, parseExperienceInput, EXPERIENCE_PROMPT_TEXT } from "../../src/lib/resumeBuilderFlow";

jest.mock("../../src/lib/resumeBuilderApi", () => ({
  ensureResumeProfile: jest.fn().mockResolvedValue({ user_id: "test-user" }),
  getResume: jest.fn().mockResolvedValue({ id: 7, declaration: "I declare this is accurate.", declaration_enabled: true }),
  updateResume: jest.fn().mockResolvedValue({ id: 7, title: "Data Analyst Resume", declaration_enabled: false }),
  analyzeResumeUpload: jest.fn().mockResolvedValue({
    parsedResume: {
      personalInfo: { fullName: "Alex Morgan", email: "alex@example.com" },
      targetRole: "Data Analyst",
      skills: [{ skill_name: "SQL" }, { skill_name: "Python" }],
      experience: [{ role: "Data Analyst Intern", company: "Acme", raw_input: "Built dashboards" }],
      education: [{ school: "State University", degree: "BCA", level: "UG" }],
      projects: [{ title: "Sales Analytics Dashboard", description: "Built with Power BI and SQL" }],
    },
    atsAnalysis: {
      normalizedScore: 78,
      score: { normalized_score: 78 },
      breakdown: {
        skills: { label: "Skills Match", earned: 24, maximum: 30 },
        experience: { label: "Experience Relevance", earned: 14, maximum: 20 },
      },
      skills: {
        matched_required: [{ skill: "SQL" }, { skill: "Python" }],
        missing_required: [{ skill: "Tableau" }],
      },
    },
  }),
  createImportDraft: jest.fn().mockResolvedValue({
    id: 42,
    title: "Data Analyst Resume",
    target_role: "Data Analyst",
  }),
  generateImportedResume: jest.fn().mockResolvedValue({
    resume: {
      id: 42,
      title: "Data Analyst Resume",
      target_role: "Data Analyst",
      summary: "Data analyst skilled in Python, SQL, and Power BI.",
    },
    role_analysis: {
      matched_skills: ["SQL", "Python", "Power BI"],
      recommended_skills_to_learn: ["Tableau"],
    },
  }),
  analyzeSavedResume: jest.fn().mockResolvedValue({
    score: { normalized_score: 88 },
    breakdown: {
      skills: { label: "Skills Match", earned: 28, maximum: 30 },
      experience: { label: "Experience Relevance", earned: 18, maximum: 20 },
    },
    skills: {
      matched_required: [{ skill: "SQL" }, { skill: "Python" }, { skill: "Power BI" }],
      missing_required: [{ skill: "Tableau" }],
    },
  }),
  listResumeTemplates: jest.fn().mockResolvedValue([
    { id: "steady-form", name: "Steady Form", description: "Clean corporate style" },
    { id: "modern-minimal", name: "Modern Minimal", description: "Contemporary style" },
  ]),
}));

describe("Resume Builder workflow", () => {
  test("normalizes concise UG and PG details without converting percentage to CGPA", () => {
    const education = parseEducationInput("UG: BCA, Nandha College, Computer Applications, 2019-2022, CGPA: 7.8; PG: MCA, KSR College, 2023-2025, Percentage: 82%");
    expect(education).toEqual([
      expect.objectContaining({ level: "UG", degree: "BCA", school: "Nandha College", start_date: "2019", end_date: "2022", cgpa: "7.8" }),
      expect.objectContaining({ level: "PG", degree: "MCA", school: "KSR College", start_date: "2023", end_date: "2025", percentage: "82%" }),
    ]);
  });

  test("accepts UG education with just a degree and institution", () => {
    expect(parseEducationInput("BCA | Nandha Arts and Science College")).toEqual([
      expect.objectContaining({ level: "UG", degree: "BCA", school: "Nandha Arts and Science College" }),
    ]);
  });

  test("accepts college-first UG wording, hyphen dates, and CGPA without rewriting it", () => {
    expect(parseEducationInput("UG: Nandha arts scincece college | BCA | 2020-2023 | cgpa 7.5")).toEqual([
      expect.objectContaining({ level: "UG", degree: "BCA", school: "Nandha arts scincece college", start_date: "2020", end_date: "2023", cgpa: "7.5" }),
    ]);
  });

  test("accepts multiple concise project details in one response", async () => {
    const result = await handleResumeBuilderText(
      { step: "awaiting_project", draft: {} },
      { id: "test-user", name: "Test User", email: "test@example.com", mobile: "", initial: "T" },
      "Sales dashboard | Power BI dashboard for sales reporting; Portfolio site using React",
    );

    expect(result.state.draft?.projects).toHaveLength(2);
    expect(result.state.draft?.projects?.[0]).toEqual(expect.objectContaining({ title: "Sales dashboard" }));
  });

  test("blocks final creation when undergraduate education is missing", async () => {
    const result = await handleResumeBuilderText(
      { step: "confirming", draft: { title: "Analyst Resume", name: "Test User", email: "test@example.com", targetRole: "Data Analyst", experienceLevel: "fresher", projects: [{ title: "Dashboard", description: "Power BI dashboard" }] } },
      { id: "test-user", name: "Test User", email: "test@example.com", mobile: "", initial: "T" },
      "create_now",
    );

    expect(result.state.step).toBe("awaiting_education");
    expect(result.state.pendingField).toBe("education.ug");
    expect(result.messages[0].text).toContain("Undergraduate education is required");
  });

  test("correcting required UG merges education and preserves the complete draft", async () => {
    const draft = {
      title: "Data analyst", name: "Rubeshkanna RS", email: "sai@gmail.com", phone: "6374831608", location: "TRICHY",
      targetRole: "DATA SCIENCETIST", experienceLevel: "fresher" as const, summary: "Verified data-analysis experience from projects and internship work.",
      skills: ["Python", "SQL", "Power BI", "Excel"],
      experience: [{ company: "Acme", role: "Data Analyst", start_date: "Jan 2024", end_date: "Present", raw_input: "Built Power BI dashboards that reduced reporting time by 30" }],
      education: [{ level: "PG", degree: "MCA", school: "KSR College", start_date: "2023", end_date: "2025", cgpa: "8.5" }],
      projects: [{ title: "Encrypted Search", description: "Developed a secure searchable-encryption project using Python." }],
      links: ["LinkedIn: https://www.linkedin.com/in/rubeshkannaravichandran", "GitHub: https://github.com/", "Portfolio: http://portfolio1-0nk0.onrender.com"],
    };
    const result = await handleResumeBuilderText(
      { step: "awaiting_education", pendingField: "education.ug", draft },
      { id: "test-user", name: "Test User", email: "test@example.com", mobile: "", initial: "T" },
      "UG: Nandha arts scincece college | BCA | 2020-2023 | cgpa 7.5",
    );

    expect(result.state.step).toBe("confirming");
    expect(result.state.pendingField).toBeUndefined();
    expect(result.state.draft).toEqual(expect.objectContaining({ summary: draft.summary, skills: draft.skills, experience: draft.experience, projects: draft.projects, links: draft.links }));
    expect(result.state.draft?.education).toEqual(expect.arrayContaining([
      expect.objectContaining({ level: "PG", degree: "MCA" }),
      expect.objectContaining({ level: "UG", degree: "BCA", school: "Nandha arts scincece college" }),
    ]));
    expect(result.messages[0].text).toContain("Projects: 1 entry");
    expect(result.messages[0].text).toContain("LinkedIn: provided");
  });

  test("skipping a required UG keeps the complete draft and stays on UG", async () => {
    const state = { step: "awaiting_education" as const, pendingField: "education.ug" as const, draft: { projects: [{ title: "Project", description: "Description" }], links: ["LinkedIn: https://linkedin.com/in/test"], education: [{ level: "PG", degree: "MCA", school: "KSR College" }] } };
    const result = await handleResumeBuilderText(state, { id: "test-user", name: "Test User", email: "test@example.com", mobile: "", initial: "T" }, "skip");
    expect(result.state).toEqual(state);
    expect(result.messages[0].text).toContain("other resume details are still saved");
  });

  test("hides a declaration without deleting its saved content", async () => {
    const result = await handleResumeBuilderText(
      { step: "completed", resumeId: 7 },
      { id: "test-user", name: "Test User", email: "test@example.com", mobile: "", initial: "T" },
      "hide declaration",
    );

    expect(result.messages[0].text).toContain("hidden");
  });

  test("the Create a resume option advances past the workflow menu", async () => {
    const result = await handleResumeBuilderText(
      createInitialResumeBuilderState(),
      { id: "test-user", name: "Test User", email: "test@example.com", mobile: "", initial: "T" },
      "new",
    );

    expect(result.state.step).toBe("awaiting_experience_level");
    expect(result.messages[0].text).not.toContain("Choose Create a resume or Upload an existing resume");
    expect(result.messages[0].options).toEqual(expect.arrayContaining([
      expect.objectContaining({ value: "fresher" }),
      expect.objectContaining({ value: "experienced" }),
    ]));
  });

  test("normalizes a portfolio URL and keeps it in the existing links collection", async () => {
    const result = await handleResumeBuilderText(
      {
        step: "awaiting_portfolio",
        draft: { title: "Data Analyst Resume", name: "Rubeshkanna", email: "rubesh@example.test", targetRole: "Data Analyst", experienceLevel: "fresher", links: ["LinkedIn: https://linkedin.com/in/rubesh"] },
      },
      { id: "test-user", name: "Test User", email: "test@example.com", mobile: "", initial: "T" },
      "rubeshkanna.dev",
    );

    expect(result.state.step).toBe("awaiting_certifications");
    expect(result.state.draft?.links).toEqual([
      "LinkedIn: https://linkedin.com/in/rubesh",
      "Portfolio: https://rubeshkanna.dev",
    ]);
  });

  test("rejects an invalid portfolio URL without advancing the workflow", async () => {
    const state = { step: "awaiting_portfolio" as const, draft: { links: [] } };
    const result = await handleResumeBuilderText(
      state,
      { id: "test-user", name: "Test User", email: "test@example.com", mobile: "", initial: "T" },
      "not a url",
    );

    expect(result.state).toEqual(state);
    expect(result.messages[0].text).toMatch(/valid URL/i);
  });

  test("collects multiple certifications and achievements with add-more and next-section transitions", async () => {
    const user = { id: "test-user", name: "Test User", email: "test@example.com", mobile: "", initial: "T" };
    const certificationResult = await handleResumeBuilderText(
      { step: "awaiting_certifications", draft: { projects: [{ title: "Dashboard", description: "Built dashboard" }], links: ["LinkedIn: https://linkedin.com/in/test"] } },
      user,
      "Microsoft Power BI Data Analyst Associate - Microsoft - 2025\nGoogle Data Analytics - Google - 2024",
    );
    expect(certificationResult.state.step).toBe("awaiting_certifications_more");
    expect(certificationResult.state.draft?.certifications).toEqual([
      expect.objectContaining({ name: "Microsoft Power BI Data Analyst Associate", issuer: "Microsoft", issue_date: "2025" }),
      expect.objectContaining({ name: "Google Data Analytics", issuer: "Google", issue_date: "2024" }),
    ]);
    expect(certificationResult.messages[0].options).toEqual(expect.arrayContaining([
      expect.objectContaining({ value: "add_another_certification" }),
      expect.objectContaining({ value: "next_section" }),
    ]));

    // Proceed to achievements section via next_section
    const toAchievements = await handleResumeBuilderText(certificationResult.state, user, "next_section");
    expect(toAchievements.state.step).toBe("awaiting_achievements");

    const achievementResult = await handleResumeBuilderText(toAchievements.state, user, "IEEE paper publication\nHackathon Winner - First place - 2025");
    expect(achievementResult.state.step).toBe("awaiting_achievements_more");
    expect(achievementResult.state.draft?.achievements).toEqual(expect.arrayContaining([
      expect.objectContaining({ title: "IEEE paper publication" }),
      expect.objectContaining({ title: "Hackathon Winner", date: "2025" }),
    ]));
    expect(achievementResult.messages[0].options).toEqual(expect.arrayContaining([
      expect.objectContaining({ value: "add_another_achievement" }),
      expect.objectContaining({ value: "next_section" }),
    ]));

    // Proceed to review
    const toReview = await handleResumeBuilderText(achievementResult.state, user, "next_section");
    expect(toReview.state.step).toBe("confirming");
    expect(toReview.messages[0].text).toContain("Certifications: 2 entry");
    expect(toReview.messages[0].text).toContain("Achievements: 2 entry");
  });

  test("projects flow offers + Add another project and allows adding a second project", async () => {
    const user = { id: "test-user", name: "Test User", email: "test@example.com", mobile: "", initial: "T" };
    // 1. Enter first project
    const step1 = await handleResumeBuilderText(
      { step: "awaiting_project", draft: { education: [{ level: "UG", degree: "BCA", school: "College" }] } },
      user,
      "E-Commerce Web App | Built online store using React and Node.js with payment integration",
    );
    expect(step1.state.step).toBe("awaiting_project_more");
    expect(step1.state.draft?.projects).toHaveLength(1);
    expect(step1.state.draft?.projects?.[0].title).toBe("E-Commerce Web App");
    expect(step1.messages[0].text).toContain("Total: 1 project");
    expect(step1.messages[0].options).toEqual(expect.arrayContaining([
      expect.objectContaining({ value: "add_another_project" }),
      expect.objectContaining({ value: "next_section" }),
    ]));

    // 2. Click "+ Add another project"
    const step2 = await handleResumeBuilderText(step1.state, user, "add_another_project");
    expect(step2.state.step).toBe("awaiting_project");
    expect(step2.messages[0].text).toContain("Add another project");

    // 3. Enter second project
    const step3 = await handleResumeBuilderText(
      step2.state,
      user,
      "AI Chatbot | Built customer service chatbot using Python and NLP",
    );
    expect(step3.state.step).toBe("awaiting_project_more");
    expect(step3.state.draft?.projects).toHaveLength(2);
    expect(step3.state.draft?.projects?.[1].title).toBe("AI Chatbot");
    expect(step3.messages[0].text).toContain("Total: 2 projects");

    // 4. Click "Go to next section (Links)"
    const step4 = await handleResumeBuilderText(step3.state, user, "next_section");
    expect(step4.state.step).toBe("awaiting_linkedin");
    expect(step4.state.draft?.projects).toHaveLength(2);
  });

  test("shows ATS Quality Advisory and enrichment option when minimal info is provided", async () => {
    const user = { id: "test-user", name: "Test User", email: "test@example.com", mobile: "", initial: "T" };
    const minimalDraft = {
      title: "Dev Resume",
      name: "Alice",
      email: "alice@example.com",
      targetRole: "Frontend Developer",
      experienceLevel: "fresher" as const,
      summary: "Short summary",
      skills: ["HTML", "CSS"],
      education: [{ level: "UG", degree: "BSc CS", school: "State University" }],
      projects: [{ title: "Portfolio", description: "Personal portfolio website" }],
      links: [],
    };

    const result = await handleResumeBuilderText(
      { step: "awaiting_achievements_more", draft: minimalDraft },
      user,
      "next_section",
    );

    expect(result.state.step).toBe("confirming");
    expect(result.messages[0].text).toContain("ATS Quality Advisory");
    expect(result.messages[0].text).toContain("minimal details");
    expect(result.messages[0].text).toContain("high ATS score (85+)");
    expect(result.messages[0].options).toEqual(expect.arrayContaining([
      expect.objectContaining({ value: "enrich_ats" }),
      expect.objectContaining({ value: "create_now" }),
    ]));

    // Selecting "enrich_ats" transitions to awaiting_enrichment_choice
    const enrichResult = await handleResumeBuilderText(result.state, user, "enrich_ats");
    expect(enrichResult.state.step).toBe("awaiting_enrichment_choice");
    expect(enrichResult.messages[0].options).toEqual(expect.arrayContaining([
      expect.objectContaining({ value: "enrich_project" }),
      expect.objectContaining({ value: "enrich_skills" }),
      expect.objectContaining({ value: "enrich_links" }),
    ]));

    // Selecting enrich_project navigates directly to project input
    const projectEnrich = await handleResumeBuilderText(enrichResult.state, user, "enrich_project");
    expect(projectEnrich.state.step).toBe("awaiting_project");
  });

  test("shows High ATS Score Ready when comprehensive details are provided", async () => {
    const user = { id: "test-user", name: "Test User", email: "test@example.com", mobile: "", initial: "T" };
    const richDraft = {
      title: "Data Scientist Resume",
      name: "Bob",
      email: "bob@example.com",
      targetRole: "Data Scientist",
      experienceLevel: "fresher" as const,
      summary: "Aspiring Data Scientist with strong machine learning, statistical modeling, and data visualization background.",
      skills: ["Python", "SQL", "Pandas", "NumPy", "Scikit-Learn", "TensorFlow", "Power BI", "Docker"],
      education: [{ level: "UG", degree: "B.Tech AI & DS", school: "Tech University" }],
      projects: [
        { title: "Customer Churn Prediction", description: "Built XGBoost classifier with 91% accuracy" },
        { title: "NLP Sentiment Analyzer", description: "Deployed BERT model on AWS with FastAPI" },
      ],
      links: ["LinkedIn: https://linkedin.com/in/bob", "GitHub: https://github.com/bob"],
      certifications: [{ name: "AWS Certified Machine Learning", issuer: "AWS", issue_date: "2025" }],
      achievements: [{ title: "Kaggle Bronze Medalist", description: "Top 10% in tabular competition" }],
    };

    const result = await handleResumeBuilderText(
      { step: "awaiting_achievements_more", draft: richDraft },
      user,
      "next_section",
    );

    expect(result.state.step).toBe("confirming");
    expect(result.messages[0].text).toContain("High ATS Score Ready");
    expect(result.messages[0].options).toEqual(expect.arrayContaining([
      expect.objectContaining({ value: "create_now" }),
    ]));
  });

  test("uploading resume without target role prompts for target role and preserves pending file", async () => {
    const user = { id: "test-user", name: "Alex Morgan", email: "alex@example.com", mobile: "", initial: "A" };
    const fakeFile = new File(["dummy resume text"], "Alex_Resume.pdf", { type: "application/pdf" });

    const result = await importResumeBuilderFile(
      createInitialResumeBuilderState(),
      user,
      fakeFile,
    );

    expect(result.state.step).toBe("awaiting_upload_role");
    expect(result.state.pendingUploadFile).toBe(fakeFile);
    expect(result.messages[0].text).toContain("what role are you targeting?");
  });

  test("entering target role after direct file upload triggers AI generation and displays ATS scorecard", async () => {
    const user = { id: "test-user", name: "Alex Morgan", email: "alex@example.com", mobile: "", initial: "A" };
    const fakeFile = new File(["dummy resume text"], "Alex_Resume.pdf", { type: "application/pdf" });

    const result = await handleResumeBuilderText(
      {
        step: "awaiting_upload_role",
        pendingUploadFile: fakeFile,
        draft: {},
      },
      user,
      "Data Analyst",
    );

    expect(result.state.step).toBe("reviewing");
    expect(result.state.resumeId).toBe(42);
    expect(result.state.atsScore).toBe(88);
    expect(result.messages[0].text).toContain("ATS Match Score: 88/100");
    expect(result.messages[0].text).toContain("**Target Role:** Data Analyst");
    expect(result.messages[0].text).toContain("AI Resume Tailoring Complete");
    expect(result.messages[0].text).toContain("Matched Skills for Data Analyst");
    expect(result.messages[0].options).toEqual(expect.arrayContaining([
      expect.objectContaining({ value: "choose_template" }),
      expect.objectContaining({ value: "edit_resume" }),
      expect.objectContaining({ value: "enrich_ats" }),
    ]));
  });

  test("uploading resume with target role already set immediately generates tailored resume and ATS scorecard", async () => {
    const user = { id: "test-user", name: "Alex Morgan", email: "alex@example.com", mobile: "", initial: "A" };
    const fakeFile = new File(["dummy resume text"], "Alex_Resume.pdf", { type: "application/pdf" });

    const result = await importResumeBuilderFile(
      {
        step: "awaiting_upload",
        draft: { targetRole: "Data Analyst", experienceLevel: "fresher" },
      },
      user,
      fakeFile,
    );

    expect(result.state.step).toBe("reviewing");
    expect(result.state.resumeId).toBe(42);
    expect(result.state.atsScore).toBe(88);
    expect(result.messages[0].text).toContain("ATS Match Score: 88/100");
    expect(result.messages[0].text).toContain("AI Resume Tailoring Complete");
  });

  test("choosing template from reviewing step presents available templates", async () => {
    const user = { id: "test-user", name: "Alex Morgan", email: "alex@example.com", mobile: "", initial: "A" };

    const result = await handleResumeBuilderText(
      {
        step: "reviewing",
        resumeId: 42,
        draft: { targetRole: "Data Analyst" },
      },
      user,
      "choose_template",
    );

    expect(result.state.step).toBe("awaiting_template");
    expect(result.messages[0].text).toContain("Choose a resume template");
    expect(result.messages[0].options).toEqual(expect.arrayContaining([
      expect.objectContaining({ value: "template:steady-form" }),
      expect.objectContaining({ value: "template:modern-minimal" }),
    ]));
  });

  test("clicking Create a resume from error state advances to awaiting_experience_level without looping", async () => {
    const user = { id: "test-user", name: "Alex Morgan", email: "alex@example.com", mobile: "", initial: "A" };

    const result = await handleResumeBuilderText(
      {
        step: "error",
        error: "Upload failed",
        draft: { targetRole: "Python Developer" },
      },
      user,
      "create_resume",
    );

    expect(result.state.step).toBe("awaiting_experience_level");
    expect(result.state.error).toBeUndefined();
    expect(result.state.draft?.targetRole).toBe("Python Developer");
    expect(result.messages[0].text).toContain("Before we begin, which best describes you?");
  });

  test("clicking Try again from upload error state preserves targetRole, jobDescription, and careerLevel", async () => {
    const user = { id: "test-user", name: "Alex Morgan", email: "alex@example.com", mobile: "", initial: "A" };

    const result = await handleResumeBuilderText(
      {
        step: "error",
        error: "Upload failed",
        draft: {
          targetRole: "Python Developer",
          jobDescription: "Web Developer",
          experienceLevel: "experienced",
        },
      },
      user,
      "retry_upload",
    );

    expect(result.state.step).toBe("awaiting_upload");
    expect(result.state.error).toBeUndefined();
    expect(result.state.draft?.targetRole).toBe("Python Developer");
    expect(result.state.draft?.jobDescription).toBe("Web Developer");
    expect(result.state.draft?.experienceLevel).toBe("experienced");
    expect(result.messages[0].text).toContain("Python Developer");
  });

  test("recognizes 'school is no problem generate me resue' fuzzy intent and triggers generation", async () => {
    const user = { id: "test-user", name: "Alex Morgan", email: "alex@example.com", mobile: "", initial: "A" };

    const result = await handleResumeBuilderText(
      {
        step: "reviewing",
        resumeId: 42,
        draft: { targetRole: "Python Developer" },
      },
      user,
      "school is no problem generate me resue",
    );

    expect(result.state.step).toBe("awaiting_template");
    expect(result.messages[0].text).toContain("Your complete, source-grounded resume wording has been generated");
  });

  test("recognizes 'school is no problem' during education step and advances without education", async () => {
    const user = { id: "test-user", name: "Alex Morgan", email: "alex@example.com", mobile: "", initial: "A" };

    const result = await handleResumeBuilderText(
      {
        step: "awaiting_education",
        draft: {
          targetRole: "Python Developer",
          skills: ["Python", "Django"],
        },
      },
      user,
      "school is no problem generate me resue",
    );

    expect(result.state.step).toBe("awaiting_project");
    expect(result.messages[0].text).toContain("No problem, we'll continue without education details");
  });

  describe("experience step natural prompt and parsing", () => {
    const user = { id: "test-user", name: "Alex Morgan", email: "alex@example.com", mobile: "", initial: "A" };

    test("Test 3: Confirm the new UI example contains no pipe '|' characters", () => {
      expect(EXPERIENCE_PROMPT_TEXT).not.toContain("|");
      expect(EXPERIENCE_PROMPT_TEXT).toContain("Company: Acme Technologies");
      expect(EXPERIENCE_PROMPT_TEXT).toContain("Role: Data Analyst");
      expect(EXPERIENCE_PROMPT_TEXT).toContain("Duration: Jan 2024 – Present");
      expect(EXPERIENCE_PROMPT_TEXT).toContain("Responsibilities:");
      expect(EXPERIENCE_PROMPT_TEXT).toContain("Type Skip if you do not want to add experience.");
    });

    test("awaiting_skills transition outputs the exact EXPERIENCE_PROMPT_TEXT without pipes", async () => {
      const result = await handleResumeBuilderText(
        { step: "awaiting_skills", draft: { experienceLevel: "fresher" } },
        user,
        "Python, SQL, Power BI",
      );
      expect(result.state.step).toBe("awaiting_experience");
      expect(result.messages[0].text).toBe(EXPERIENCE_PROMPT_TEXT);
      expect(result.messages[0].text).not.toContain("|");
    });

    test("Test 1: Structured natural format (Format A) is correctly parsed and advances", async () => {
      const input = `Company: Acme Technologies
Role: Data Analyst
Duration: Jan 2024 – Present

Responsibilities:
• Developed Power BI dashboards for business reporting.
• Analyzed data using SQL and Excel.
• Automated recurring reports and generated business insights.`;

      const parsed = parseExperienceInput(input);
      expect(parsed).toHaveLength(1);
      expect(parsed[0].company).toBe("Acme Technologies");
      expect(parsed[0].role).toBe("Data Analyst");
      expect(parsed[0].start_date).toBe("Jan 2024");
      expect(parsed[0].end_date).toBe("Present");
      expect(parsed[0].is_current).toBe(true);
      expect(parsed[0].raw_input).toContain("Developed Power BI dashboards for business reporting.");
      expect(parsed[0].raw_input).toContain("Analyzed data using SQL and Excel.");

      const result = await handleResumeBuilderText(
        { step: "awaiting_experience", draft: { skills: ["Python", "SQL"] } },
        user,
        input,
      );
      expect(result.state.step).toBe("awaiting_experience_more");
      expect(result.state.draft?.experience).toHaveLength(1);
      expect(result.state.draft?.experience?.[0].company).toBe("Acme Technologies");
      expect(result.state.draft?.experience?.[0].role).toBe("Data Analyst");
      expect(result.messages[0].text).toContain("Added experience: Acme Technologies (Data Analyst)");
    });

    test("Test 2: Natural paragraph format (Format C)", () => {
      const input = "I worked as a Python Developer at ABC Technologies from January 2024 to December 2025. I developed Flask APIs and worked with MySQL.";
      const parsed = parseExperienceInput(input);
      expect(parsed).toHaveLength(1);
      expect(parsed[0].company).toBe("ABC Technologies");
      expect(parsed[0].role).toBe("Python Developer");
      expect(parsed[0].start_date).toBe("January 2024");
      expect(parsed[0].end_date).toBe("December 2025");
      expect(parsed[0].raw_input).toContain("Flask APIs and worked with MySQL");
    });

    test("Format C with 'currently working there'", () => {
      const input = "I worked as a Data Analyst Intern at DigiDARA Technologies from January 2025 and I am currently working there. My responsibilities include Power BI dashboards, SQL analysis, and data cleaning.";
      const parsed = parseExperienceInput(input);
      expect(parsed).toHaveLength(1);
      expect(parsed[0].company).toBe("DigiDARA Technologies");
      expect(parsed[0].role).toBe("Data Analyst Intern");
      expect(parsed[0].start_date).toBe("January 2025");
      expect(parsed[0].end_date).toBe("Present");
      expect(parsed[0].is_current).toBe(true);
      expect(parsed[0].raw_input).toContain("Power BI dashboards");
    });

    test("Format B: Multiline blocks without labels", () => {
      const input = `DigiDARA Technologies
Data Analyst Intern
Jan 2025 – Present

Created Power BI dashboards and performed SQL data analysis.`;
      const parsed = parseExperienceInput(input);
      expect(parsed).toHaveLength(1);
      expect(parsed[0].company).toBe("DigiDARA Technologies");
      expect(parsed[0].role).toBe("Data Analyst Intern");
      expect(parsed[0].start_date).toBe("Jan 2025");
      expect(parsed[0].end_date).toBe("Present");
      expect(parsed[0].is_current).toBe(true);
      expect(parsed[0].raw_input).toContain("Created Power BI dashboards");
    });

    test("Format D: Concise role at company", () => {
      const input = `Data Analyst Intern at DigiDARA Technologies
January 2025 - Present

Worked on Power BI dashboards, SQL queries, data cleaning and reporting.`;
      const parsed = parseExperienceInput(input);
      expect(parsed).toHaveLength(1);
      expect(parsed[0].company).toBe("DigiDARA Technologies");
      expect(parsed[0].role).toBe("Data Analyst Intern");
      expect(parsed[0].start_date).toBe("January 2025");
      expect(parsed[0].end_date).toBe("Present");
      expect(parsed[0].is_current).toBe(true);
      expect(parsed[0].raw_input).toContain("Worked on Power BI dashboards");
    });

    test("Supports Achievements: and Responsibilities & Achievements: headings", () => {
      const input = `Company: ABC Technologies
Role: Python Developer
Duration: Jan 2024 – Present

Achievements:
• Built REST APIs using Flask.
• Reduced API response time through query optimization.
• Integrated MySQL with the application.`;

      const parsed = parseExperienceInput(input);
      expect(parsed).toHaveLength(1);
      expect(parsed[0].company).toBe("ABC Technologies");
      expect(parsed[0].role).toBe("Python Developer");
      expect(parsed[0].raw_input).toContain("Built REST APIs using Flask.");
      expect(parsed[0].raw_input).toContain("Reduced API response time");
    });

    test("Test 4: Skip produces empty experience section without errors", async () => {
      const result = await handleResumeBuilderText(
        { step: "awaiting_experience", draft: { skills: ["Python"] } },
        user,
        "Skip",
      );
      expect(result.state.step).toBe("awaiting_education");
      expect(result.state.draft?.experience || []).toEqual([]);
    });

    test("Test 5: Multiple experience entries preserved separately", async () => {
      const input = `Company: DigiDARA Technologies
Role: Data Analyst Intern
Duration: Jan 2025 – Present

Responsibilities:
• Developed Power BI dashboards.
• Worked with SQL and Python.
• Performed data cleaning and analysis.

Company: ABC Technologies
Role: Python Developer
Duration: Jun 2024 – Dec 2024

Responsibilities:
• Developed Flask APIs.
• Integrated MySQL databases.
• Fixed application bugs.`;

      const parsed = parseExperienceInput(input);
      expect(parsed).toHaveLength(2);
      expect(parsed[0].company).toBe("DigiDARA Technologies");
      expect(parsed[0].role).toBe("Data Analyst Intern");
      expect(parsed[1].company).toBe("ABC Technologies");
      expect(parsed[1].role).toBe("Python Developer");

      const result = await handleResumeBuilderText(
        { step: "awaiting_experience", draft: { skills: ["Python"] } },
        user,
        input,
      );
      expect(result.state.step).toBe("awaiting_experience_more");
      expect(result.state.draft?.experience).toHaveLength(2);
      expect(result.state.draft?.experience?.[0].company).toBe("DigiDARA Technologies");
      expect(result.state.draft?.experience?.[1].company).toBe("ABC Technologies");
      expect(result.messages[0].text).toContain("Total: 2 entries");
    });

    test("Backward compatibility: legacy pipe input still parses cleanly", () => {
      const input = "Acme | Data Analyst | Jan 2024 | Present | Built Power BI dashboards that reduced reporting time by 30%.";
      const parsed = parseExperienceInput(input);
      expect(parsed).toHaveLength(1);
      expect(parsed[0].company).toBe("Acme");
      expect(parsed[0].role).toBe("Data Analyst");
      expect(parsed[0].start_date).toBe("Jan 2024");
      expect(parsed[0].end_date).toBe("Present");
      expect(parsed[0].is_current).toBe(true);
      expect(parsed[0].raw_input).toContain("Built Power BI dashboards");
    });
  });
});


