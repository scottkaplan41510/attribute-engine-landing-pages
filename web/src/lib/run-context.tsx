"use client";

import { createContext, useContext, useEffect, useState } from "react";
import { sample, type Result } from "@/lib/results";

const KEY = "last-run";
const Context = createContext<{ result: Result; setResult: (r: Result) => void }>({ result: sample, setResult: () => {} });

export function RunProvider({ children }: { children: React.ReactNode }) {
  const [result, set] = useState<Result>(sample);
  useEffect(() => {
    try {
      const saved = sessionStorage.getItem(KEY);
      if (saved) set(JSON.parse(saved));
    } catch {}
  }, []);
  const setResult = (r: Result) => {
    set(r);
    try {
      if (r === sample) sessionStorage.removeItem(KEY);
      else sessionStorage.setItem(KEY, JSON.stringify(r));
    } catch {}
  };
  return <Context.Provider value={{ result, setResult }}>{children}</Context.Provider>;
}

export const useRun = () => useContext(Context);
