jest.mock('../../src/lib/authApi', () => ({
  sendEmailCode: jest.fn(),
  verifyEmailCode: jest.fn(),
}));

import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import VerifyEmailScreen from '../../src/components/VerifyEmailScreen';
import * as authApi from '../../src/lib/authApi';

const mocked = jest.mocked(authApi);
const verifiedUser = { id: 'u1', name: 'Asha', email: 'asha@example.com', mobile: null, is_admin: false, consent_accepted_at: null, consent_policy_version: null, email_verified: true, verification_required: false };

beforeEach(() => {
  jest.clearAllMocks();
  localStorage.setItem('digidara_token', 'tok');
});

function renderScreen() {
  const onVerified = jest.fn();
  const onLogout = jest.fn();
  render(<VerifyEmailScreen email="asha@example.com" onVerified={onVerified} onLogout={onLogout} />);
  return { onVerified, onLogout };
}

test('says where the code went and verifies a 6-digit code', async () => {
  mocked.verifyEmailCode.mockResolvedValue(verifiedUser);
  const { onVerified } = renderScreen();
  expect(screen.getByRole('status')).toHaveTextContent('We sent a 6-digit code to asha@example.com');
  const input = screen.getByLabelText('Verification code');
  fireEvent.change(input, { target: { value: '12a 3-456' } });
  expect(input).toHaveValue('123456');                    // digits only
  fireEvent.click(screen.getByRole('button', { name: 'Verify email' }));
  await waitFor(() => expect(onVerified).toHaveBeenCalledWith(verifiedUser));
  expect(mocked.verifyEmailCode).toHaveBeenCalledWith('tok', '123456');
});

test('a wrong code shows the server message', async () => {
  mocked.verifyEmailCode.mockRejectedValue(new Error('That code is not right. 4 tries left.'));
  const { onVerified } = renderScreen();
  fireEvent.change(screen.getByLabelText('Verification code'), { target: { value: '000000' } });
  fireEvent.click(screen.getByRole('button', { name: 'Verify email' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('4 tries left');
  expect(onVerified).not.toHaveBeenCalled();
});

test('the button waits for all 6 digits', () => {
  renderScreen();
  fireEvent.change(screen.getByLabelText('Verification code'), { target: { value: '123' } });
  expect(screen.getByRole('button', { name: 'Verify email' })).toBeDisabled();
});

test('a new code can be requested, and the cooldown message is shown', async () => {
  mocked.sendEmailCode.mockResolvedValueOnce({ message: "We've sent a 6-digit code to your email." });
  renderScreen();
  fireEvent.click(screen.getByRole('button', { name: 'Send a new code' }));
  await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent("We've sent a 6-digit code to your email. Check your spam folder too."));
  mocked.sendEmailCode.mockRejectedValueOnce(new Error('Please wait 42 seconds before asking for a new code.'));
  fireEvent.click(screen.getByRole('button', { name: 'Send a new code' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('wait 42 seconds');
});

test('the learner can switch to a different account', () => {
  const { onLogout } = renderScreen();
  fireEvent.click(screen.getByRole('button', { name: 'Use a different account' }));
  expect(onLogout).toHaveBeenCalled();
});
