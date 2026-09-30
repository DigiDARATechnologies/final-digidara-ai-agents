jest.mock('../../src/lib/certificateAgentApi', () => ({
  downloadExamReportPdf: jest.fn(),
  sendCertificateChatMessage: jest.fn(),
}));
import { handleCertificateText, type CertificateFlowState } from '../../src/lib/certificateAgentFlow';
import { downloadExamReportPdf, sendCertificateChatMessage } from '../../src/lib/certificateAgentApi';

const passedExam: CertificateFlowState = {
  step: 'completed', token: 'token', mode: 'chat', sessionId: 'session', passed: true, certificateId: 42, hasCompletedExam: true,
};

beforeAll(() => {
  URL.createObjectURL = jest.fn(() => 'blob:report');
  URL.revokeObjectURL = jest.fn();
  jest.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined);
});

beforeEach(() => {
  jest.mocked(downloadExamReportPdf).mockResolvedValue({ blob: new Blob(['%PDF']), filename: 'exam_report.pdf' } as never);
});

test('after the exam report is downloaded, the certificate buttons are offered again', async () => {
  const result = await handleCertificateText(passedExam, 'download_exam_report');
  expect(downloadExamReportPdf).toHaveBeenCalledWith('token', { sessionId: 'session' });
  expect(result.messages[0].text).toContain('Your exam report has been downloaded');
  expect(result.messages[0].options?.map((option) => option.value)).toEqual([
    'download_42', 'download_exam_report', 'change_certificate_name', 'email_certificate', 'my_certificates', 'start_exam',
  ]);
});

test('without a certificate (a failed exam), the report download offers the same buttons as the result', async () => {
  const result = await handleCertificateText({ ...passedExam, passed: false, certificateId: undefined }, 'download_exam_report');
  expect(result.messages[0].options?.map((option) => option.value)).toEqual(['download_exam_report', 'start_exam', 'menu']);
});

test('the buttons at the end of the exam are unchanged', async () => {
  jest.mocked(sendCertificateChatMessage).mockResolvedValue({
    messages: [{ role: 'assistant', content: 'You PASSED', metadata: { certificate_id: 42, certificate_number: 'DG-42' } }],
    status: { session_status: 'completed', passed: true, current_question_index: 30, total_questions: 30, score_percentage: 90 },
  } as never);
  const result = await handleCertificateText({ step: 'awaiting_chat_session', token: 'token', sessionId: 'session', mode: 'chat', currentQuestionIndex: 29 }, 'Option A');
  expect(result.state.certificateId).toBe(42);
  expect(result.messages.at(-1)?.options?.map((option) => option.value)).toEqual([
    'download_42', 'download_exam_report', 'change_certificate_name', 'email_certificate', 'my_certificates', 'start_exam',
  ]);
});
