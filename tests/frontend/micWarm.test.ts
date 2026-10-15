import { acquireMicrophone, releaseWarmMicrophone, warmMicrophone } from '../../src/lib/micWarm';

function fakeStream(readyState = 'live') {
  const track = { readyState, stop: jest.fn() };
  return { stream: { getAudioTracks: () => [track], getTracks: () => [track] } as unknown as MediaStream, track };
}

describe('warmed microphone', () => {
  const getUserMedia = jest.fn();
  beforeEach(() => {
    getUserMedia.mockReset();
    Object.defineProperty(global.navigator, 'mediaDevices', { value: { getUserMedia }, configurable: true });
  });

  test('the first recording takes the stream opened ahead of time', async () => {
    const { stream } = fakeStream();
    getUserMedia.mockResolvedValue(stream);
    warmMicrophone();
    warmMicrophone();
    expect(await acquireMicrophone()).toBe(stream);
    expect(getUserMedia).toHaveBeenCalledTimes(1);
  });

  test('a stream that ended is replaced by a fresh one', async () => {
    const ended = fakeStream('ended');
    const fresh = fakeStream();
    getUserMedia.mockResolvedValueOnce(ended.stream).mockResolvedValueOnce(fresh.stream);
    warmMicrophone();
    expect(await acquireMicrophone()).toBe(fresh.stream);
  });

  test('without a warm stream a recording opens the microphone itself', async () => {
    const { stream } = fakeStream();
    getUserMedia.mockResolvedValue(stream);
    expect(await acquireMicrophone()).toBe(stream);
  });

  test('an unused warm stream is closed on release', async () => {
    const { stream, track } = fakeStream();
    getUserMedia.mockResolvedValue(stream);
    warmMicrophone();
    releaseWarmMicrophone();
    await Promise.resolve();
    await Promise.resolve();
    expect(track.stop).toHaveBeenCalled();
  });
});
