jest.mock('../../src/lib/resumeBuilderApi', () => ({
  analyzeResumeUpload: jest.fn(),
  analyzeSavedResume: jest.fn(),
  createImportDraft: jest.fn(),
  createResume: jest.fn(),
  exportResumePdf: jest.fn(),
  generateImportedResume: jest.fn(),
  getResume: jest.fn(),
  listResumeTemplates: jest.fn(),
  previewResumePdf: jest.fn(),
  selectResumeTemplate: jest.fn(),
  suggestResumeEdit: jest.fn(),
  updateResume: jest.fn(),
}));

import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import ResumeCanvas from '../../src/components/ResumeCanvas';
import { createInitialResumeCanvasState, type ResumeCanvasState } from '../../src/lib/resumeCanvasState';
import * as api from '../../src/lib/resumeBuilderApi';

const user = { id: 'u1', name: 'Asha Rao', email: 'asha@example.com', mobile: '9999999999', initial: 'A' };

const doc = { id: 7, title: 'Asha Rao Resume', target_role: 'Data Analyst', summary: '', skills: [{ skill_name: 'SQL' }], experience: [], education: [], projects: [], template_choice: 'steady-form' };
const analysis = { score: { normalized_score: 55 }, skills: { missing_required: ['Python', 'Tableau'], matched_required: ['SQL'] }, breakdown: {} };

beforeEach(() => {
  jest.clearAllMocks();
  jest.mocked(api.listResumeTemplates).mockResolvedValue([{ id: 'steady-form', name: 'Steady Form' }]);
  jest.mocked(api.getResume).mockResolvedValue(doc);
  jest.mocked(api.analyzeSavedResume).mockResolvedValue(analysis);
  jest.mocked(api.previewResumePdf).mockResolvedValue(new Blob(['%PDF'], { type: 'application/pdf' }));
});

function renderCanvas(state: ResumeCanvasState = createInitialResumeCanvasState(), onStateChange = jest.fn()) {
  return { onStateChange, ...render(<ResumeCanvas user={user} state={state} onStateChange={onStateChange} />) };
}

describe('starting a resume', () => {
  test('shows the three ways to start, not a step-by-step Q&A', () => {
    renderCanvas();
    expect(screen.getByText('Upload a resume')).toBeInTheDocument();
    expect(screen.getByText('Start fresh')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Target role (e.g. Data Analyst)')).toBeInTheDocument();
  });

  test('uploading a file imports, generates wording, and lands in the workspace', async () => {
    jest.mocked(api.analyzeResumeUpload).mockResolvedValue({ parsedResume: { title: 'x' }, atsAnalysis: {} });
    jest.mocked(api.createImportDraft).mockResolvedValue({ id: 9, target_role: 'Data Analyst' });
    jest.mocked(api.generateImportedResume).mockResolvedValue({ resume: { summary: 'Generated summary' } });
    jest.mocked(api.updateResume).mockResolvedValue(doc);
    const { onStateChange } = renderCanvas();

    const file = new File(['resume text'], 'resume.pdf', { type: 'application/pdf' });
    fireEvent.change(document.querySelector('input[type="file"]')!, { target: { files: [file] } });

    await waitFor(() => expect(jest.mocked(api.createImportDraft)).toHaveBeenCalledWith('u1', 'resume.pdf', { title: 'x' }, {}, '', 'fresher'));
    await waitFor(() => expect(jest.mocked(api.updateResume)).toHaveBeenCalledWith('u1', 9, { summary: 'Generated summary' }));
    await waitFor(() => expect(onStateChange).toHaveBeenCalledWith(expect.objectContaining({ resumeId: 9 })));
    await waitFor(() => expect(screen.getByDisplayValue('Asha Rao Resume')).toBeInTheDocument());
  });

  test('the 5-question interview creates a resume directly, with the signed-in contact info', async () => {
    jest.mocked(api.createResume).mockResolvedValue({ id: 11 });
    const { onStateChange } = renderCanvas();

    fireEvent.change(screen.getByPlaceholderText('Target role (e.g. Data Analyst)'), { target: { value: 'Backend Engineer' } });
    fireEvent.change(screen.getByPlaceholderText('Top skills, comma separated'), { target: { value: 'Java, Spring' } });
    fireEvent.change(screen.getByPlaceholderText('One achievement you\'re proud of'), { target: { value: 'Shipped a payments service' } });
    fireEvent.click(screen.getByRole('button', { name: 'Create my first draft' }));

    await waitFor(() => expect(jest.mocked(api.createResume)).toHaveBeenCalledWith('u1', expect.objectContaining({
      target_role: 'Backend Engineer',
      personal_info: { name: 'Asha Rao', email: 'asha@example.com', phone: '9999999999' },
      skills: [{ skill_name: 'Java' }, { skill_name: 'Spring' }],
      achievements: [{ title: 'Shipped a payments service' }],
    })));
    await waitFor(() => expect(onStateChange).toHaveBeenCalledWith(expect.objectContaining({ resumeId: 11 })));
  });

  test('a failed start shows the reason and lets the student try again', async () => {
    jest.mocked(api.createResume).mockRejectedValue(new Error('The service is busy.'));
    renderCanvas();
    fireEvent.click(screen.getByRole('button', { name: 'Create my first draft' }));
    expect(await screen.findByText('The service is busy.')).toBeInTheDocument();
    expect(screen.getByText('Start fresh')).toBeInTheDocument();
  });
});

describe('the workspace: live resume, score panel, and copilot', () => {
  const withResume: ResumeCanvasState = { step: 'editing', resumeId: 7, resumeTitle: doc.title, atsScore: 55 };

  test('loads the saved document and its score, with no step-by-step questions', async () => {
    renderCanvas(withResume);
    expect(await screen.findByDisplayValue('Asha Rao Resume')).toBeInTheDocument();
    expect(screen.getByDisplayValue('Data Analyst')).toBeInTheDocument();
    expect(await screen.findByText('55/100')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Missing: Python/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Missing: Tableau/ })).toBeInTheDocument();
  });

  test('editing a field autosaves and refreshes the score', async () => {
    jest.useFakeTimers({ advanceTimers: true });
    jest.mocked(api.updateResume).mockResolvedValue({ ...doc, summary: 'A data analyst with 3 years experience.' });
    jest.mocked(api.analyzeSavedResume).mockResolvedValueOnce(analysis).mockResolvedValue({ score: { normalized_score: 72 }, skills: {}, breakdown: {} });
    renderCanvas(withResume);
    const summaryBox = await screen.findByPlaceholderText('Add a summary here');
    fireEvent.change(summaryBox, { target: { value: 'A data analyst with 3 years experience.' } });
    jest.advanceTimersByTime(800);
    await waitFor(() => expect(jest.mocked(api.updateResume)).toHaveBeenCalledWith('u1', 7, { summary: 'A data analyst with 3 years experience.' }));
    jest.useRealTimers();
  });

  test('a missing-skill chip sends a targeted instruction straight to the copilot', async () => {
    jest.mocked(api.suggestResumeEdit).mockResolvedValue({ resume: { ...doc, skills: [...doc.skills, { skill_name: 'Python' }] }, changes: ['Added Python to skills'], warnings: [], requires_confirmation: true });
    renderCanvas(withResume);
    fireEvent.click(await screen.findByRole('button', { name: /Missing: Python/ }));
    await waitFor(() => expect(jest.mocked(api.suggestResumeEdit)).toHaveBeenCalledWith('u1', expect.objectContaining({ title: doc.title }), expect.stringContaining('Python')));
    expect(await screen.findByText('Added Python to skills')).toBeInTheDocument();
  });

  test('propose -> Apply saves the proposed resume and refreshes the score', async () => {
    const proposed = { ...doc, summary: 'Punchier summary.' };
    jest.mocked(api.suggestResumeEdit).mockResolvedValue({ resume: proposed, changes: ['Rewrote the summary'], warnings: [], requires_confirmation: true });
    jest.mocked(api.updateResume).mockResolvedValue(proposed);
    renderCanvas(withResume);
    const chatBox = await screen.findByPlaceholderText('Tell me what to change…');
    fireEvent.change(chatBox, { target: { value: 'make my summary punchier' } });
    fireEvent.click(screen.getByRole('button', { name: 'Send' }));
    expect(await screen.findByText('Rewrote the summary')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Apply' }));
    await waitFor(() => expect(jest.mocked(api.updateResume)).toHaveBeenCalledWith('u1', 7, proposed));
    await waitFor(() => expect(screen.queryByText('Rewrote the summary')).toBeNull());
  });

  test('Cancel discards the proposal without saving anything', async () => {
    jest.mocked(api.suggestResumeEdit).mockResolvedValue({ resume: { ...doc, summary: 'x' }, changes: ['Rewrote the summary'], warnings: [], requires_confirmation: true });
    renderCanvas(withResume);
    fireEvent.change(await screen.findByPlaceholderText('Tell me what to change…'), { target: { value: 'change it' } });
    fireEvent.click(screen.getByRole('button', { name: 'Send' }));
    await screen.findByText('Rewrote the summary');
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    expect(screen.queryByText('Rewrote the summary')).toBeNull();
    expect(jest.mocked(api.updateResume)).not.toHaveBeenCalled();
  });

  test('a failed copilot request shows the reason', async () => {
    jest.mocked(api.suggestResumeEdit).mockRejectedValue(new Error('The AI service is temporarily unavailable.'));
    renderCanvas(withResume);
    fireEvent.change(await screen.findByPlaceholderText('Tell me what to change…'), { target: { value: 'change it' } });
    fireEvent.click(screen.getByRole('button', { name: 'Send' }));
    expect(await screen.findByText('The AI service is temporarily unavailable.')).toBeInTheDocument();
  });

  test('pasting a job description tailors through the same propose/apply pipeline', async () => {
    jest.mocked(api.suggestResumeEdit).mockResolvedValue({ resume: { ...doc, summary: 'Tailored.' }, changes: ['Tailored to the job description'], warnings: [], requires_confirmation: true });
    renderCanvas(withResume);
    fireEvent.change(await screen.findByPlaceholderText('Paste a job description…'), { target: { value: 'We need a SQL-savvy analyst...' } });
    fireEvent.click(screen.getByRole('button', { name: 'Tailor my resume' }));
    await waitFor(() => expect(jest.mocked(api.suggestResumeEdit)).toHaveBeenCalledWith('u1', expect.anything(), expect.stringContaining('We need a SQL-savvy analyst')));
    expect(await screen.findByText('Tailored to the job description')).toBeInTheDocument();
  });

  test('choosing a template and downloading uses the saved resume id', async () => {
    jest.mocked(api.exportResumePdf).mockResolvedValue({ blob: new Blob(['%PDF'], { type: 'application/pdf' }), filename: 'Asha-Rao.pdf' });
    renderCanvas(withResume);
    await screen.findByDisplayValue('Asha Rao Resume');
    fireEvent.click(screen.getByRole('button', { name: /Download PDF/ }));
    await waitFor(() => expect(jest.mocked(api.exportResumePdf)).toHaveBeenCalledWith('u1', 7, 'steady-form'));
  });

  test('reports its progress back to the parent chat for the notification bell', async () => {
    const onStateChange = jest.fn();
    renderCanvas(withResume, onStateChange);
    await waitFor(() => expect(onStateChange).toHaveBeenCalledWith({ step: 'editing', resumeId: 7, resumeTitle: 'Asha Rao Resume', atsScore: 55 }));
  });

  test('a high score is reported as ready, matching the notification wording', async () => {
    jest.mocked(api.analyzeSavedResume).mockResolvedValue({ score: { normalized_score: 88 }, skills: {}, breakdown: {} });
    const onStateChange = jest.fn();
    renderCanvas(withResume, onStateChange);
    await waitFor(() => expect(onStateChange).toHaveBeenCalledWith(expect.objectContaining({ step: 'ready', atsScore: 88 })));
  });
});
