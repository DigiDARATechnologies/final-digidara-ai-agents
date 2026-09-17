export function createSingleFlight<Args extends unknown[], Result>(
  keyFor: (...args: Args) => string,
  execute: (...args: Args) => Promise<Result>,
) {
  let pending: { key: string; promise: Promise<Result> } | undefined;
  return (...args: Args): Promise<Result> => {
    const key = keyFor(...args);
    if (pending?.key === key) return pending.promise;
    const promise = execute(...args);
    pending = { key, promise };
    const clear = () => { if (pending?.promise === promise) pending = undefined; };
    promise.then(clear, clear);
    return promise;
  };
}
