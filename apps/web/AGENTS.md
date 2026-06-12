<!-- BEGIN:nextjs-agent-rules -->
# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` before writing any code. Heed deprecation notices.
<!-- END:nextjs-agent-rules -->

## Testing patterns (vitest + @testing-library/react)

### Hook tests must use `renderHook`
React hooks (`useStore`, `useState`, `useCallback`, etc.) cannot be called directly in test functions. Always use `renderHook` from `@testing-library/react`:
```ts
import { renderHook } from "@testing-library/react";
const { result } = renderHook(() => useMyHook());
expect(result.current.something).toBe(...);
```

### Zustand store state
Set store state directly before rendering:
```ts
import { useAppStore } from "@/lib/store";
useAppStore.setState({ demoToken: null, demoApiKey: null });
```

### localStorage mock must use `vi.hoisted`
If any imported module references `window.localStorage` at module evaluation time (e.g. store.ts), the mock must be placed in `vi.hoisted()` before the import:
```ts
vi.hoisted(() => {
  const store: Record<string, string> = {};
  Object.defineProperty(window, "localStorage", {
    value: {
      getItem: (key: string) => store[key] ?? null,
      setItem: (key: string, value: string) => { store[key] = value; },
      removeItem: (key: string) => { delete store[key]; },
    },
    writable: true, configurable: true,
  });
});
import { useAppStore } from "@/lib/store"; // safe
```

### Component tests
- Use `@testing-library/react` (`render`, `screen`)
- Test `<BackendGap>` on 501/404 per project convention
- Test a11y attributes (`aria-label`, `role`, keyboard nav via `userEvent.tab()`)

### Run command
```bash
npx vitest run                                        # all tests
npx vitest run --reporter=verbose <path>               # single file
npx vitest run --reporter=verbose src/hooks/my-hook.test.ts
```
