import { describe, it, expect, vi } from "vitest";
import { render, screen, act, waitFor } from "@testing-library/react";
import { useState, useEffect } from "react";
import { useLocalStorage } from "./use-local-storage";

function createMockStorage() {
  const store = new Map<string, string>();
  return {
    getItem: (key: string) => store.get(key) ?? null,
    setItem: (key: string, value: string) => store.set(key, value),
    removeItem: (key: string) => store.delete(key),
    clear: () => store.clear(),
  } as Storage;
}

describe("useLocalStorage", () => {
  beforeEach(() => {
    Object.defineProperty(globalThis, "localStorage", {
      value: createMockStorage(),
      writable: true,
      configurable: true,
    });
    vi.clearAllMocks();
  });

  it("does not cause an infinite render loop when setValue is called from useEffect", async () => {
    // This mirrors UploadPage: a state derived from localStorage, with an effect
    // that persists it back. If setValue is unstable, the effect re-runs forever.
    function MirrorComponent() {
      const [stored, setStored] = useLocalStorage<number>("loop-test", 0);
      const [derived, setDerived] = useState(stored);

      useEffect(() => {
        setStored(derived);
      }, [derived, setStored]);

      return (
        <button onClick={() => setDerived((d) => d + 1)}>
          count:{derived}
        </button>
      );
    }

    render(<MirrorComponent />);

    const button = screen.getByRole("button");
    expect(button).toHaveTextContent("count:0");

    await act(async () => {
      button.click();
    });

    await waitFor(() => {
      expect(button).toHaveTextContent("count:1");
    });
  });

  it("keeps setValue reference stable across renders", () => {
    const setValues: Array<(value: number | ((val: number) => number)) => void> = [];

    function Collector() {
      const [, setValue] = useLocalStorage<number>("stable-test", 0);
      setValues.push(setValue);
      return null;
    }

    const { rerender } = render(<Collector />);
    rerender(<Collector />);
    rerender(<Collector />);

    expect(setValues.length).toBe(3);
    expect(new Set(setValues).size).toBe(1);
  });

  it("writes and reads values from localStorage", () => {
    function Writer() {
      const [value, setValue] = useLocalStorage("persist-test", { count: 0 });
      return (
        <button onClick={() => setValue({ count: 5 })}>
          count:{value.count}
        </button>
      );
    }

    render(<Writer />);
    screen.getByRole("button").click();

    expect(JSON.parse(localStorage.getItem("persist-test") || "{}")).toEqual({ count: 5 });
  });

  it("removes value from localStorage", () => {
    function Remover() {
      const [value, setValue, remove] = useLocalStorage("remove-test", 1);
      return (
        <div>
          <span>{value}</span>
          <button onClick={() => setValue(42)}>set</button>
          <button onClick={() => remove()}>remove</button>
        </div>
      );
    }

    render(<Remover />);
    screen.getByRole("button", { name: "set" }).click();
    expect(JSON.parse(localStorage.getItem("remove-test") || "null")).toBe(42);

    screen.getByRole("button", { name: "remove" }).click();
    expect(localStorage.getItem("remove-test")).toBeNull();
  });
});
