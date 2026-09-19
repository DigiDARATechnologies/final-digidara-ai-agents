function serializeError(error) {
  if (!error) return null;
  return {
    name: error.name || "Error",
    message: error.message || String(error),
    request_id: error.requestId || null,
  };
}

export function logClientEvent(level, event, message, context = {}) {
  const normalizedLevel = ["debug", "info", "warn", "error"].includes(level)
    ? level
    : "info";
  const { error, ...safeContext } = context;
  const payload = {
    timestamp: new Date().toISOString(),
    level: normalizedLevel,
    event,
    message,
    ...safeContext,
  };
  const serializedError = serializeError(error);
  if (serializedError) payload.error = serializedError;

  const writer = console[normalizedLevel] || console.log;
  writer(JSON.stringify(payload));
}

export function reportClientError(event, error, context = {}) {
  logClientEvent(
    "error",
    event,
    error?.message || "Unexpected client error",
    { ...context, error }
  );
}

export function reportClientWarning(event, error, context = {}) {
  logClientEvent(
    "warn",
    event,
    error?.message || "Client fallback activated",
    { ...context, error }
  );
}
