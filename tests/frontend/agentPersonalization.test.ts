/** Every agent's chat opens from what onboarding collected instead of asking again. */
jest.mock('../../src/lib/codeforgeApi', () => ({
  getProblem: jest.fn(), submitMcqAnswer: jest.fn(), runProblem: jest.fn(), submitProblem: jest.fn(), askTutor: jest.fn(),
  ensureSession: jest.fn(), listCourses: jest.fn(), listTechnologies: jest.fn(), listTopics: jest.fn(), listProblems: jest.fn(),
  listLevelProblems: jest.fn(),
}));
jest.mock('../../src/lib/mockInterviewApi', () => ({
  ensureMockInterviewSession: jest.fn(), getActiveMockInterview: jest.fn(), startMockInterview: jest.fn(),
  submitMockInterviewAnswer: jest.fn(), endMockInterview: jest.fn(), exitMockInterview: jest.fn(),
}));
jest.mock('../../src/lib/capstoneApi', () => ({
  askProjectQuestion: jest.fn(), checkEligibilityFree: jest.fn(), chooseTopic: jest.fn(), confirmTimer: jest.fn(),
  downloadFinalReport: jest.fn(), getThreadStatus: jest.fn(), startVivaAttempt: jest.fn(), submitVivaAnswer: jest.fn(),
  topicIntakeTurn: jest.fn(), uploadSubmission: jest.fn(),
}));
jest.mock('../../src/lib/jobFetchApi', () => ({
  getJobFeed: jest.fn(), chatWithJobAgent: jest.fn(), ensureJobFetchProfile: jest.fn(), getJobFetchProfile: jest.fn(),
  updateJobFetchProfile: jest.fn(), ensureJobConversation: jest.fn(), jobFetchAction: jest.fn(), uploadJobFetchResume: jest.fn(),
}));

import * as codeforgeApi from '../../src/lib/codeforgeApi';
import * as jobApi from '../../src/lib/jobFetchApi';
import * as mockApi from '../../src/lib/mockInterviewApi';
import { createInitialCapstoneState, initialCapstoneMessage } from '../../src/lib/capstoneFlow';
import { openCodeForgeChat } from '../../src/lib/codeforgeFlow';
import { openJobFetchChat } from '../../src/lib/jobFetchFlow';
import { goalMatchScore, setLearnerContext } from '../../src/lib/learnerContext';
import type { LearnerSummary } from '../../src/lib/learnerApi';
import { handleMockInterviewText, openMockInterviewChat } from '../../src/lib/mockInterviewFlow';

const user = { id: 'u1', name: 'Prem Kumar', email: 'prem@example.com', mobile: '', initial: 'P' };

function learner(levels: Record<string, string> = {}): LearnerSummary {
  return {
    profile: { target_role: 'ai engineer', degree: 'M.Sc', skills: ['python', 'llm', 'langgraph', 'rag'], experience: 'experienced',
      onboarding_completed: true, onboarding_completed_at: '2026-10-08T00:00:00' },
    levels: Object.entries(levels).map(([agent_name, level]) => ({ agent_name, agent_label: agent_name, level: level as never, source: 'self', updated_at: null })),
    level_choices: [], consent_required: false, membership: null,
  };
}

const COURSES = [
  { id: 1, name: 'Data Analytics', slug: 'data-analytics', description: 'Cleaning, querying and explaining data.', icon: '', technology_count: 1 },
  { id: 2, name: 'AI and Machine Learning', slug: 'ai-ml', description: 'Python and numerical foundations for ML.', icon: '', technology_count: 1 },
  { id: 3, name: 'Generative AI and Agentic AI', slug: 'genai', description: 'Python foundations behind modern AI applications.', icon: '', technology_count: 1 },
];

afterEach(() => setLearnerContext(null));

test('without a profile every agent opens exactly as before', async () => {
  jest.mocked(mockApi.ensureMockInterviewSession).mockResolvedValue({ sessionToken: 't', student_id: 1 });
  jest.mocked(mockApi.getActiveMockInterview).mockResolvedValue({ active: false });
  const { messages } = await openMockInterviewChat(user);
  expect(messages[0].options?.map((o) => o.value)).toEqual(['technical', 'hr']);
  expect(initialCapstoneMessage(user).options).toBeUndefined();
  expect(createInitialCapstoneState(user).difficulty).toBe('easy');
});

test('coding practice recommends the course that fits the goal', async () => {
  setLearnerContext(learner());
  jest.mocked(codeforgeApi.ensureSession).mockResolvedValue({ sessionToken: 's', student: { display_name: 'Prem Kumar' } } as never);
  jest.mocked(codeforgeApi.listCourses).mockResolvedValue({ courses: COURSES } as never);
  const { messages } = await openCodeForgeChat(user);
  expect(messages[0].text).toContain('For your goal (AI Engineer · python, llm, langgraph, rag), I recommend **Generative AI and Agentic AI**');
  // The problem list comes first, then the courses, best fit first.
  expect(messages[0].options?.[0]).toMatchObject({ value: '__problemset__' });
  expect(messages[0].options?.[1]).toMatchObject({ value: 'genai', label: '⭐ Generative AI and Agentic AI · recommended for you' });
});

test('mock interview offers the target role at the learner level, straight to the question count', async () => {
  setLearnerContext(learner({ mock_interview_agent: 'hard' }));
  jest.mocked(mockApi.ensureMockInterviewSession).mockResolvedValue({ sessionToken: 't', student_id: 1 });
  jest.mocked(mockApi.getActiveMockInterview).mockResolvedValue({ active: false });
  const opened = await openMockInterviewChat(user);
  expect(opened.messages[0].options?.[0]).toMatchObject({ value: 'profile_role', label: 'Technical interview for AI Engineer' });
  const next = await handleMockInterviewText(opened.state, user, 'profile_role');
  expect(next.state).toMatchObject({ roundType: 'technical', interviewMode: 'role', roleName: 'AI Engineer', difficulty: 'advanced', step: 'choose_question_count' });
});

test('capstone offers a project around the profile, at the learner level', () => {
  setLearnerContext(learner({ capstone_project_agent: 'medium' }));
  const message = initialCapstoneMessage(user);
  expect(message.text).toContain('Based on your profile (AI Engineer · python, llm, langgraph, rag)');
  expect(message.options?.[0]).toMatchObject({ label: 'AI Engineer project', value: 'AI Engineer using python, llm, langgraph', suggested: true });
  expect(message.text).toContain('type any other language, role or topic');
  expect(createInitialCapstoneState(user).difficulty).toBe('medium');
});

test('the job agent fills only the empty fields of its profile from onboarding', async () => {
  setLearnerContext({ ...learner(), profile: { ...learner().profile, experience: 'fresher' } });
  const empty = { user_id: 'u1', full_name: null, skills: [], preferred_titles: [], preferred_locations: [], preferred_work_mode: '',
    experience_years: 0, experience_provided: false, resume_url: '', resume_original_name: null, profile_completed: false,
    onboarding_prompt: 'Which city would you like to work in?', plan_tier: 'free' };
  jest.mocked(jobApi.getJobFetchProfile).mockResolvedValueOnce(empty).mockResolvedValueOnce({ ...empty, full_name: 'Prem Kumar' });
  jest.mocked(jobApi.updateJobFetchProfile).mockResolvedValue({ message: 'ok', profile_completed: false });
  await openJobFetchChat(user);
  expect(jobApi.updateJobFetchProfile).toHaveBeenCalledWith(expect.objectContaining({
    full_name: 'Prem Kumar', skills: ['python', 'llm', 'langgraph', 'rag'], preferred_titles: ['AI Engineer'], experience_years: 0,
  }));
});

test('goal matching links roles and skills to course names', () => {
  const goal = { targetRole: 'data analyst', degree: '', skills: ['excel', 'sql'], experience: 'fresher' as const };
  expect(goalMatchScore(goal, 'Data Analytics')).toBeGreaterThan(goalMatchScore(goal, 'Generative AI and Agentic AI'));
  expect(goalMatchScore({ ...goal, skills: ['c'] }, 'Code Playground')).toBe(0);
});

test('coding practice is by level: a technology lists only the level\'s problems, across topics', async () => {
  const { handleCodeForgeText } = await import('../../src/lib/codeforgeFlow');
  setLearnerContext(learner({ codeforge_agent: 'beginner' }));
  const problem = (slug: string, name: string, topic: string, progress = 'Not Started') => ({
    id: slug.length, name, slug, description: '', difficulty: 'Easy', max_score: 100, language: 'python', sequence: 1,
    progress, best_score: progress === 'Solved' ? 100 : 0, attempts: progress === 'Solved' ? 1 : 0,
    topic_slug: topic, topic_name: topic === 'intro' ? 'Introduction' : 'Loops',
  });
  const state = {
    step: 'awaiting_technology' as const, sessionToken: 's', courses: [], topics: [], problems: [],
    courseSlug: 'genai', courseName: 'Generative AI', technologies: [{ id: 1, name: 'Python', slug: 'python', description: '', icon: '', topic_count: 9 }],
  };
  jest.mocked(codeforgeApi.listLevelProblems).mockResolvedValueOnce({
    problems: [problem('greet', 'Print a Greeting', 'intro', 'Solved'), problem('count', 'Count to Ten', 'loops')],
  } as never);
  const listed = await handleCodeForgeText(state as never, 'python');
  expect(codeforgeApi.listLevelProblems).toHaveBeenCalledWith('s', 'genai', 'python', 'easy');
  expect(codeforgeApi.listTopics).not.toHaveBeenCalled();
  expect(listed.messages[0].text).toBe('Python · Beginner level: 2 Easy problems, 1 solved. Pick one in the problem list; solve all of them to unlock the next level.');
  // The problems open in the problem list (a table), not as chat buttons.
  expect(listed.openProblemSet).toEqual({ courseSlug: 'genai', technologySlug: 'python' });
  expect(listed.messages[0].options?.map((o) => o.label)).toEqual(['📋 Python problem list', 'Other technology', 'Back to courses']);

  jest.mocked(codeforgeApi.getProblem).mockResolvedValueOnce({ problem: { ...problem('count', 'Count to Ten', 'loops'), question_type: 'code',
    input_format: '', output_format: '', constraints: '', examples: [], starter_code: '' } } as never);
  const opened = await handleCodeForgeText(listed.state, 'count');
  // The problem is opened in its own topic, which the level list carries.
  expect(codeforgeApi.getProblem).toHaveBeenCalledWith('s', 'genai', 'python', 'loops', 'count');
  expect(opened.state.step).toBe('awaiting_code');
});
