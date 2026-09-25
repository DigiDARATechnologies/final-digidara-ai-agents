jest.mock('../../src/lib/capstoneApi', () => ({
  askProjectQuestion: jest.fn(),
  checkEligibilityFree: jest.fn(),
  chooseTopic: jest.fn(),
  clarifyTopicRequest: jest.fn(),
  confirmTimer: jest.fn(),
  getThreadStatus: jest.fn(),
  submitVivaAnswer: jest.fn(),
  uploadSubmission: jest.fn(),
}));
import { formatSyntaxError, formatSyntaxErrorMessage, mergeCapstoneFiles, submitCapstoneFiles, type CapstoneFlowState } from '../../src/lib/capstoneFlow';
import * as api from '../../src/lib/capstoneApi';

const docx = new File(['d'], 'report.docx');
const zip = new File(['z'], 'project.zip');
const ready: CapstoneFlowState = {
  step: 'awaiting_submission',
  name: 'Learner', email: 'learner@example.test', phone: '', difficulty: 'easy',
  threadId: 'thread', docxFile: docx, zipFile: zip,
};
const pythonError = { path: 'Tracker/src/main.py', language: 'Python', line: 12, column: 11, message: "'(' was never closed", source_line: 'print(total' };

afterEach(() => jest.clearAllMocks());

describe('formatSyntaxError', () => {
  test('lays the error out like a terminal: file and line, the source line, a caret under the column, the message', () => {
    expect(formatSyntaxError(pythonError)).toBe(
      ['  File "Tracker/src/main.py", line 12', '    print(total', '              ^', "SyntaxError: '(' was never closed"].join('\n'),
    );
  });

  test('the caret sits under the reported column, whatever the indentation of the source line', () => {
    // column is 1-based: column 19 is the "(" after "sum" in an 8-space-indented line.
    const lines = formatSyntaxError({ ...pythonError, source_line: '        return sum(items', column: 19 }).split('\n');
    expect(lines[1]).toContain('return sum(items');
    expect(lines[2].indexOf('^')).toBe(lines[1].indexOf('('));
  });

  test('non-Python languages are named, and a missing line/column/source degrades gracefully', () => {
    expect(formatSyntaxError({ path: 'data.json', language: 'JSON', line: 3, column: 5, message: 'Expecting value', source_line: '  "a": ,' }))
      .toContain('JSON syntax error: Expecting value');
    expect(formatSyntaxError({ path: 'x.py', language: 'Python', message: 'bad' })).toBe('  File "x.py"\nSyntaxError: bad');
  });
});

describe('formatSyntaxErrorMessage', () => {
  test('one error: a heading, one fenced terminal block, and no "Revision needed" wording anywhere', () => {
    const text = formatSyntaxErrorMessage([pythonError]);
    expect(text).toContain('### Syntax error in your code');
    expect(text.match(/```/g)).toHaveLength(2);
    expect(text).toContain("SyntaxError: '(' was never closed");
    expect(text).not.toMatch(/revision needed/i);
    expect(text).not.toMatch(/fix the issues/i);
  });

  test('several errors: a counted heading and one fenced block each', () => {
    const text = formatSyntaxErrorMessage([pythonError, { ...pythonError, path: 'Tracker/src/util.py', line: 3 }]);
    expect(text).toContain('### 2 syntax errors in your code');
    expect(text.match(/```/g)).toHaveLength(4);
    expect(text).toContain('Tracker/src/util.py');
  });

  test('other problems found in the same submission follow the errors', () => {
    const text = formatSyntaxErrorMessage([pythonError], 'Report: the Approach section is only placeholder text.');
    expect(text).toContain('Report: the Approach section is only placeholder text.');
    expect(text.indexOf('```')).toBeLessThan(text.indexOf('Report: the Approach'));
  });
});

describe('submitCapstoneFiles with syntax errors', () => {
  test('shows the errors instead of a generic revision message, and reopens the upload', async () => {
    jest.mocked(api.uploadSubmission).mockResolvedValue({
      thread_id: 'thread', status: 'needs_revision', submission_id: 's1', revision_notes: '', final_score: null, syntax_errors: [pythonError],
    });
    const result = await submitCapstoneFiles(ready);
    expect(result.messages).toHaveLength(1);
    expect(result.messages[0].text).toContain('### Syntax error in your code');
    expect(result.messages[0].text).toContain('  File "Tracker/src/main.py", line 12');
    expect(result.messages[0].text).not.toMatch(/revision needed/i);
    expect(result.state.step).toBe('awaiting_submission');
    expect(result.state.docxFile).toBeUndefined();
    expect(result.state.zipFile).toBeUndefined();
  });

  test('after a syntax failure the student can attach both files again straight away', async () => {
    jest.mocked(api.uploadSubmission).mockResolvedValue({
      thread_id: 'thread', status: 'needs_revision', revision_notes: '', syntax_errors: [pythonError],
    });
    const failed = await submitCapstoneFiles(ready);
    const merged = mergeCapstoneFiles(failed.state, [docx, zip]);
    expect(merged.state.docxFile).toBe(docx);
    expect(merged.state.zipFile).toBe(zip);
  });

  test('a normal revision (no syntax errors) keeps its existing "Revision needed" message', async () => {
    jest.mocked(api.uploadSubmission).mockResolvedValue({
      thread_id: 'thread', status: 'needs_revision', revision_notes: 'Report: add more detail.', syntax_errors: null,
    });
    const result = await submitCapstoneFiles(ready);
    expect(result.messages[0].text).toContain('Revision needed:');
    expect(result.messages[0].text).toContain('Report: add more detail.');
  });
});
