jest.mock('../../src/lib/certificateAgentApi', () => ({ sendCertificateChatMessage: jest.fn() }));

import { handleCertificateText, type CertificateFlowState } from '../../src/lib/certificateAgentFlow';
import * as api from '../../src/lib/certificateAgentApi';

const exam = { step: 'awaiting_chat_session', token: 't', sessionId: 's', currentQuestionIndex: 22, totalQuestions: 30 } as unknown as CertificateFlowState;
const next = { role: 'assistant', content: 'Question 24 of 30:\nWhat is a view?', metadata: { options: ['A', 'B', 'C', 'D'] } };

test('when a reply was lost, the exam catches up to the question the server is on', async () => {
  jest.mocked(api.sendCertificateChatMessage).mockResolvedValueOnce({ messages: [next], status: { stale: true, current_question_index: 23 } } as never);
  const result = await handleCertificateText(exam, 'A');
  expect(result.state.currentQuestionIndex).toBe(23);
  expect(result.messages[0].text).toContain('Question 24');
  expect(result.messages[0].options?.map((option) => option.value)).toEqual(['A', 'B', 'C', 'D']);
});

test('a double click is still ignored', async () => {
  jest.mocked(api.sendCertificateChatMessage).mockResolvedValueOnce({ messages: [next], status: { stale: true, current_question_index: 22 } } as never);
  const result = await handleCertificateText(exam, 'A');
  expect(result.stale).toBe(true);
  expect(result.messages).toEqual([]);
  expect(result.state.currentQuestionIndex).toBe(22);
});
