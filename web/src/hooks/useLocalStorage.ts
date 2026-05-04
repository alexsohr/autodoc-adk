import { useState, useCallback, useEffect, useRef } from "react";

const KEY_PREFIX = "autodoc:";

function isLocalStorageAvailable(): boolean {
  try {
    const testKey = "__autodoc_ls_test__";
    window.localStorage.setItem(testKey, "1");
    window.localStorage.removeItem(testKey);
    return true;
  } catch {
    return false;
  }
}

function readValue<T>(key: string, initialValue: T): T {
  if (!isLocalStorageAvailable()) {
    return initialValue;
  }
  try {
    const raw = window.localStorage.getItem(`${KEY_PREFIX}${key}`);
    return raw !== null ? (JSON.parse(raw) as T) : initialValue;
  } catch {
    return initialValue;
  }
}

/**
 * Generic typed hook that reads/writes to LocalStorage with an `autodoc:` key prefix.
 * Falls back to in-memory state if LocalStorage is unavailable.
 */
export function useLocalStorage<T>(
  key: string,
  initialValue: T,
): [T, (value: T | ((prev: T) => T)) => void] {
  const [storedValue, setStoredValue] = useState<T>(() =>
    readValue(key, initialValue),
  );

  // Keep a ref so the event listener always sees the latest value
  const storedValueRef = useRef(storedValue);
  storedValueRef.current = storedValue;

  const setValue = useCallback(
    (value: T | ((prev: T) => T)) => {
      setStoredValue((prev) => {
        const nextValue =
          value instanceof Function ? value(prev) : value;

        if (isLocalStorageAvailable()) {
          try {
            window.localStorage.setItem(
              `${KEY_PREFIX}${key}`,
              JSON.stringify(nextValue),
            );
          } catch {
            // Storage full or blocked — value is still kept in memory
          }
        }

        return nextValue;
      });
    },
    [key],
  );

  // Sync across tabs via the storage event
  useEffect(() => {
    function handleStorageChange(event: StorageEvent) {
      if (event.key !== `${KEY_PREFIX}${key}`) return;
      try {
        const newValue =
          event.newValue !== null
            ? (JSON.parse(event.newValue) as T)
            : initialValue;
        setStoredValue(newValue);
      } catch {
        // Ignore malformed JSON from other sources
      }
    }

    window.addEventListener("storage", handleStorageChange);
    return () => window.removeEventListener("storage", handleStorageChange);
  }, [key, initialValue]);

  return [storedValue, setValue];
}
