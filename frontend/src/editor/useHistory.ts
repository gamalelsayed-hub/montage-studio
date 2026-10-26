import { useCallback, useRef, useState } from "react";

const LIMIT = 200;

/**
 * تاريخ للتراجع (Undo) والإعادة (Redo).
 * set(next) بيسجّل خطوة. set(next, false) بيغيّر من غير تسجيل (أثناء السحب)،
 * وقبلها checkpoint() بيحفظ الحالة اللي قبل السحب كخطوة واحدة.
 */
export function useHistory<T>(initial: T) {
  const [present, setPresent] = useState(initial);
  const past = useRef<T[]>([]);
  const future = useRef<T[]>([]);
  const presentRef = useRef(initial);
  const [, force] = useState(0);

  const push = (state: T) => {
    past.current.push(state);
    if (past.current.length > LIMIT) past.current.shift();
    future.current = [];
  };

  const set = useCallback((next: T | ((prev: T) => T), record = true) => {
    const value = typeof next === "function" ? (next as (p: T) => T)(presentRef.current) : next;
    if (record) push(presentRef.current);
    presentRef.current = value;
    setPresent(value);
  }, []);

  const checkpoint = useCallback(() => {
    push(presentRef.current);
    force((n) => n + 1);
  }, []);

  const undo = useCallback(() => {
    const previous = past.current.pop();
    if (previous === undefined) return;
    future.current.push(presentRef.current);
    presentRef.current = previous;
    setPresent(previous);
  }, []);

  const redo = useCallback(() => {
    const next = future.current.pop();
    if (next === undefined) return;
    past.current.push(presentRef.current);
    presentRef.current = next;
    setPresent(next);
  }, []);

  return {
    present,
    set,
    checkpoint,
    undo,
    redo,
    canUndo: past.current.length > 0,
    canRedo: future.current.length > 0,
  };
}
