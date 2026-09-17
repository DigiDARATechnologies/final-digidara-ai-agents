import { createSingleFlight } from '../../src/lib/singleFlight';
import { aptitudeTimezonePayload } from '../../src/lib/aptitudeTimezone';


test('deduplicates identical Start requests while batch generation is pending', async () => {
  let complete!: (value: { test_id: string; status: string }) => void;
  const response = new Promise<{ test_id: string; status: string }>((resolve) => {
    complete = resolve;
  });
  const execute = jest.fn(() => response);
  const createAptitudeTest = createSingleFlight(
    (sessionToken: string, payload: Record<string, unknown>) =>
      JSON.stringify([sessionToken, payload]),
    execute,
  );

  const payload = { mode: 'mixed', technical_language: 'Python' };
  const first = createAptitudeTest('session', payload);
  const duplicate = createAptitudeTest('session', payload);

  expect(execute).toHaveBeenCalledTimes(1);
  expect(duplicate).toBe(first);
  complete({ test_id: 'test-1', status: 'ready' });
  await expect(first).resolves.toEqual({ test_id: 'test-1', status: 'ready' });
});

test('attaches the browser IANA timezone to the create-test API payload', () => {
  const payload = aptitudeTimezonePayload('create_test', { mode: 'mixed' });
  const browserZone = Intl.DateTimeFormat().resolvedOptions().timeZone;
  expect(payload.timezone).toBe(browserZone === 'Asia/Calcutta' ? 'Asia/Kolkata' : browserZone);
});

test('attaches the browser IANA timezone to the PDF-download API payload', () => {
  const payload = aptitudeTimezonePayload('download_report', { test_id: 'timezone-test' });
  const browserZone = Intl.DateTimeFormat().resolvedOptions().timeZone;
  expect(payload.timezone).toBe(browserZone === 'Asia/Calcutta' ? 'Asia/Kolkata' : browserZone);
});

test('preserves an explicitly supplied valid or legacy timezone value', () => {
  const payload = aptitudeTimezonePayload('create_test', { timezone: 'Asia/Kolkata' });
  expect(payload.timezone).toBe('Asia/Kolkata');
});

test('normalizes the legacy India timezone alias returned by some browsers', () => {
  const original = Intl.DateTimeFormat;
  jest.spyOn(Intl, 'DateTimeFormat').mockImplementation((...args) => {
    const formatter = new original(...args);
    return { ...formatter, resolvedOptions: () => ({ ...formatter.resolvedOptions(), timeZone: 'Asia/Calcutta' }) } as Intl.DateTimeFormat;
  });
  expect(aptitudeTimezonePayload('create_test', {}).timezone).toBe('Asia/Kolkata');
  jest.restoreAllMocks();
});

test('does not add timezone to unrelated agent requests', () => {
  const payload = aptitudeTimezonePayload('question', { test_id: 'timezone-test' });
  expect(payload).toEqual({ test_id: 'timezone-test' });
});
