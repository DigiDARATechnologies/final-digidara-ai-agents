import { acquireMicrophone, releaseWarmMicrophone, warmMicrophone } from '../../src/lib/micWarm';

function fakeStream(readyState = 'live') {
  const track = { readyState, stop: jest.fn() };
  const clone = { getAudioTracks: () => [{ readyState: 'live', stop: jest.fn() }], getTracks: () => [] };
  const stream = { getAudioTracks: () => [track], getTracks: () => [track], clone: jest.fn(() => clone) };
  return { stream: stream as unknown as MediaStream, track, clone };
}

describe('the microphone held for a voice conversation', () => {
  const getUserMedia = jest.fn();
  beforeEach(() => {
    releaseWarmMicrophone();
    getUserMedia.mockReset();
    Object.defineProperty(global.navigator, 'mediaDevices', { value: { getUserMedia }, configurable: true });
  });

  test('every recording gets a clone of the one open stream, which stays open', async () => {
    const { stream, track, clone } = fakeStream();
    getUserMedia.mockResolvedValue(stream);
    warmMicrophone();
    warmMicrophone();
    expect(await acquireMicrophone()).toBe(clone);
    expect(await acquireMicrophone()).toBe(clone);
    expect(getUserMedia).toHaveBeenCalledTimes(1);
    expect(track.stop).not.toHaveBeenCalled();
  });

  test('a stream that ended is replaced by a fresh one', async () => {
    const ended = fakeStream('ended');
    const fresh = fakeStream();
    getUserMedia.mockResolvedValueOnce(ended.stream).mockResolvedValueOnce(fresh.stream);
    warmMicrophone();
    expect(await acquireMicrophone()).toBe(fresh.stream);
  });

  test('without a held stream a recording opens the microphone itself', async () => {
    const { stream } = fakeStream();
    getUserMedia.mockResolvedValue(stream);
    expect(await acquireMicrophone()).toBe(stream);
  });

  test('the held microphone is closed on release', async () => {
    const { stream, track } = fakeStream();
    getUserMedia.mockResolvedValue(stream);
    warmMicrophone();
    releaseWarmMicrophone();
    await Promise.resolve();
    await Promise.resolve();
    expect(track.stop).toHaveBeenCalled();
  });
});
