import { useEffect, useState } from "react";
import { load, save } from "../lib/storage.js";

// useState persisted in localStorage. `normalize` cleans what is read (old or corrupt data).
export function useLocalStorage(key, initial, normalize = (x) => x) {
  const [value, setValue] = useState(() => normalize(load(key, initial)));
  useEffect(() => {
    save(key, value);
  }, [key, value]);
  return [value, setValue];
}
