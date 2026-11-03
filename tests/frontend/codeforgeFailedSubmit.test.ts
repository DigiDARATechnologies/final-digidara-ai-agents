jest.mock('../../src/lib/codeforgeApi', () => ({ submitProblem: jest.fn() }));

import { submitCodeForgeCode, type CodeForgeFlowState } from '../../src/lib/codeforgeFlow';
import * as api from '../../src/lib/codeforgeApi';

const state = {
  step: 'awaiting_code', sessionToken: 't', problemId: 1, technologyName: 'Python',
  problems: [{ slug: 'one', name: 'One', status: 'Attempted' }, { slug: 'two', name: 'Two', status: 'Not started' }],
  problemSlug: 'one',
} as unknown as CodeForgeFlowState;
const test1 = { hidden: false, passed: true, label: 'Public test 1', status: 'Accepted' };
const hidden = { hidden: true, passed: false, label: 'Hidden test 2', status: 'Wrong Answer' };

test('a failed submission can still move on, and says what a hidden test means', async () => {
  jest.mocked(api.submitProblem).mockResolvedValueOnce({ mode: 'submit', status: 'Partial', passedTests: 1, totalTests: 2, score: 50, tests: [test1, hidden] } as never);
  const result = await submitCodeForgeCode(state, 'print(1)');
  const values = result.messages[0].options?.map((option) => option.value);
  expect(values).toContain('explain_error');
  expect(values).toContain('__problemset__');
  expect(values).toContain('two');
  expect(result.messages[0].text).toContain('A hidden test checks another case');
  expect(result.state.step).toBe('awaiting_code');
});

test('a failed public test shows its own details, not the hidden test note', async () => {
  jest.mocked(api.submitProblem).mockResolvedValueOnce({ mode: 'submit', status: 'Wrong Answer', passedTests: 0, totalTests: 1, score: 0, tests: [{ ...test1, passed: false, status: 'Wrong Answer', input: '1', expectedOutput: '2', actualOutput: '3' }] } as never);
  const result = await submitCodeForgeCode(state, 'print(3)');
  expect(result.messages[0].text).toContain('Expected: 2');
  expect(result.messages[0].text).not.toContain('hidden test checks');
});
