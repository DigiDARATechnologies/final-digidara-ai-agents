jest.mock('../../src/lib/aptitudeApi', () => ({ getMixedTestConfig: jest.fn(), saveMixedTestConfig: jest.fn() }));

import { act, fireEvent, render, screen } from '@testing-library/react';
import AptitudePracticePanel from '../../src/components/AptitudePracticePanel';
import type { AptitudeFlowState } from '../../src/lib/aptitudeFlow';

function activeState(mode: 'mixed' | 'category_practice', count: number): AptitudeFlowState {
  return {
    step: 'awaiting_question', mode, sessionToken: 'session', testId: 'test',
    question: {
      test_id: 'test', sequence: 1, total_questions: count, category: 'Logical Reasoning',
      topic: 'Patterns', difficulty: 'Easy', question: 'Which pattern?',
      options: { A: 'First', B: 'Second' }, allowed_time_seconds: 60,
      total_duration_seconds: count * 60, deadline_at_ms: Date.now() + 60_000,
      hints_remaining: 2, status: 'unanswered',
      navigation: Array.from({ length: count }, (_, index) => ({ sequence: index + 1, status: 'unanswered' as const, visited: index === 0 })),
    },
  };
}

afterEach(() => jest.useRealTimers());

test.each([['mixed', 18], ['category_practice', 10]] as const)('%s Exit Test confirms before ending the attempt', (mode, count) => {
  jest.useFakeTimers().setSystemTime(new Date('2026-09-17T12:00:00Z'));
  const onChoose = jest.fn();
  const onExpire = jest.fn();
  render(<AptitudePracticePanel state={activeState(mode, count)} onChoose={onChoose} onExpire={onExpire} />);
  expect(screen.getByLabelText('Question navigation').querySelectorAll('button')).toHaveLength(count);
  fireEvent.click(screen.getByRole('button', { name: 'Exit Test' }));
  expect(screen.getByRole('alertdialog')).toHaveTextContent('cannot continue it');
  expect(onChoose).not.toHaveBeenCalled();
  act(() => jest.advanceTimersByTime(2_000));
  expect(screen.getByRole('timer')).toHaveTextContent('0:58');
  fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
  expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument();
  expect(onChoose).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: 'Exit Test' }));
  fireEvent.click(screen.getByRole('alertdialog').querySelector('.aptitude-exit-confirm') as HTMLElement);
  expect(onChoose).toHaveBeenCalledWith('exit test');
  expect(onExpire).not.toHaveBeenCalled();
});

test('the overall timer can expire while Exit confirmation is open', () => {
  jest.useFakeTimers().setSystemTime(new Date('2026-09-17T12:00:00Z'));
  const onChoose = jest.fn();
  const onExpire = jest.fn();
  render(<AptitudePracticePanel state={activeState('mixed', 18)} onChoose={onChoose} onExpire={onExpire} />);
  fireEvent.click(screen.getByRole('button', { name: 'Exit Test' }));
  act(() => jest.advanceTimersByTime(61_000));
  expect(onExpire).toHaveBeenCalledTimes(1);
  expect(onChoose).not.toHaveBeenCalled();
});
