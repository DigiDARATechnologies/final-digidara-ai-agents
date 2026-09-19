import { useEffect, useRef, useState } from "react";

export default function useInterviewTimer({ timeLimitSec, captureGenerationRef, onTimeExpired }) {
  const [timeLeft, setTimeLeft] = useState(timeLimitSec);
  const timeExpiredRef = useRef(false);
  const timeLeftRef = useRef(timeLimitSec);
  const startTimeRef = useRef(null);
  const timerRef = useRef(null);
  const timerGenerationRef = useRef(0);
  const onTimeExpiredRef = useRef(onTimeExpired);

  useEffect(() => {
    onTimeExpiredRef.current = onTimeExpired;
  }, [onTimeExpired]);

  const clearTimer = () => clearInterval(timerRef.current);
  const startTimer = ({ reset = true } = {}) => {
    clearTimer();
    const timerGeneration = captureGenerationRef.current;
    timerGenerationRef.current = timerGeneration;
    if (reset) {
      timeLeftRef.current = timeLimitSec;
      setTimeLeft(timeLimitSec);
      startTimeRef.current = Date.now();
    }
    timerRef.current = setInterval(() => {
      setTimeLeft((prev) => {
      if (prev <= 1) {
        clearTimer();
        timeLeftRef.current = 0;
        if (timerGenerationRef.current !== timerGeneration) return 0;
        timeExpiredRef.current = true;
        onTimeExpiredRef.current?.();
          return 0;
        }
        timeLeftRef.current = prev - 1;
        return timeLeftRef.current;
      });
    }, 1000);
  };

  useEffect(() => clearTimer, []);

  return { timeLeft, timeExpiredRef, timeLeftRef, startTimeRef, timerGenerationRef, startTimer, clearTimer };
}
