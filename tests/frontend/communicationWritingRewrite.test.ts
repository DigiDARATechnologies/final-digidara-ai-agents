jest.mock('../../src/lib/communicationApi', () => ({ respondWriting: jest.fn() }));

import { handleCommunicationText } from '../../src/lib/communicationFlow';
import * as api from '../../src/lib/communicationApi';

describe('rewriting a paragraph until it is right', () => {
  const scored = { step: 'writing_result', authToken: 't', sessionId: 5, writingMode: 'write', difficulty: 'easy', lastParagraph: 'I goes to school.' };

  test('offers the rewrite, puts the paragraph in the box, and scores it as a new attempt', async () => {
    const started = await handleCommunicationText(scored as never, 'rewrite_paragraph');
    expect(started.state.step).toBe('writing_turn');
    expect(started.state.rewriteDraft).toBe('I goes to school.');
    jest.mocked(api.respondWriting).mockResolvedValueOnce({ feedback: { short_feedback: 'Better.' } } as never);
    const again = await handleCommunicationText(started.state, 'I go to school.');
    expect(api.respondWriting).toHaveBeenCalledWith('t', 5, 'I go to school.', true, true);
    expect(again.state.step).toBe('writing_result');
    expect(again.state.lastParagraph).toBe('I go to school.');
    expect(again.state.rewriteDraft).toBeUndefined();
    expect(again.messages[0].options?.map((option) => option.value)).toEqual(['rewrite_paragraph', 'end_session']);
  });
});
