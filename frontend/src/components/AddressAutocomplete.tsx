import { useEffect, useRef, useState } from "react";

import { geocode } from "../api/client";

export type ResolvedLocation = {
  label: string;
  lat: number;
  lng: number;
};

type Props = {
  id: string;
  label: string;
  placeholder?: string;
  token?: string;
  disabled?: boolean;
  initialLabel?: string;
  onResolve: (loc: ResolvedLocation) => void;
  onClear: () => void;
};

const DEBOUNCE_MS = 280;
const MIN_CHARS = 3;

export function AddressAutocomplete({ id, label, placeholder, token, disabled, initialLabel, onResolve, onClear }: Props) {
  const [value, setValue] = useState(initialLabel ?? "");
  const [results, setResults] = useState<ResolvedLocation[]>([]);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const [resolved, setResolved] = useState(!!initialLabel);
  const [activeIndex, setActiveIndex] = useState(-1);
  const [fetchError, setFetchError] = useState(false);

  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    function handlePointerDown(e: PointerEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("pointerdown", handlePointerDown);
    return () => document.removeEventListener("pointerdown", handlePointerDown);
  }, []);

  function handleChange(raw: string) {
    setValue(raw);
    setResolved(false);
    setActiveIndex(-1);

    // Only propagate clear when the field is actually empty
    if (raw.trim() === "") {
      onClear();
      setFetchError(false);
    }

    if (debounceRef.current) clearTimeout(debounceRef.current);

    if (raw.trim().length < MIN_CHARS) {
      setResults([]);
      setOpen(false);
      return;
    }

    debounceRef.current = setTimeout(async () => {
      setLoading(true);
      setFetchError(false);
      try {
        const data = await geocode(raw, token);
        setResults(data.results.slice(0, 6));
        setOpen(data.results.length > 0);
      } catch (err) {
        console.error("Geocode error:", err);
        setFetchError(true);
        setResults([]);
        setOpen(false);
      } finally {
        setLoading(false);
      }
    }, DEBOUNCE_MS);
  }

  function selectResult(loc: ResolvedLocation) {
    setValue(loc.label);
    setResolved(true);
    setOpen(false);
    setResults([]);
    setActiveIndex(-1);
    onResolve(loc);
    inputRef.current?.blur();
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (!open || results.length === 0) return;

    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIndex((i) => Math.min(i + 1, results.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIndex((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      const target = activeIndex >= 0 ? results[activeIndex] : results[0];
      if (target) selectResult(target);
    } else if (e.key === "Escape") {
      setOpen(false);
    }
  }

  function handleClear() {
    setValue("");
    setResolved(false);
    setResults([]);
    setOpen(false);
    onClear();
    inputRef.current?.focus();
  }

  return (
    <div className="autocomplete-field" ref={containerRef}>
      <label htmlFor={id} className="autocomplete-label">{label}</label>
      <div className="autocomplete-input-wrap">
        <input
          ref={inputRef}
          id={id}
          className={`form-input autocomplete-input${resolved ? " resolved" : ""}`}
          type="text"
          autoComplete="off"
          spellCheck={false}
          value={value}
          placeholder={placeholder}
          disabled={disabled}
          onChange={(e) => handleChange(e.target.value)}
          onKeyDown={handleKeyDown}
          onFocus={() => { if (results.length > 0) setOpen(true); }}
          aria-expanded={open}
          aria-autocomplete="list"
          aria-controls={`${id}-listbox`}
          aria-activedescendant={activeIndex >= 0 ? `${id}-option-${activeIndex}` : undefined}
          role="combobox"
        />
        {loading && <span className="autocomplete-spinner"><span className="spinner" /></span>}
        {resolved && (
          <span className="autocomplete-check">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="20 6 9 17 4 12" />
            </svg>
          </span>
        )}
        {value && !loading && (
          <button
            type="button"
            className="autocomplete-clear"
            tabIndex={-1}
            onClick={handleClear}
            aria-label="Clear"
          >
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        )}
      </div>

      {fetchError && (
        <p className="autocomplete-fetch-error">Search unavailable — check API connection</p>
      )}

      {open && results.length > 0 && (
        <ul
          className="autocomplete-dropdown"
          id={`${id}-listbox`}
          role="listbox"
          aria-label={`${label} suggestions`}
        >
          {results.map((r, i) => {
            const [primary, ...rest] = r.label.split(", ");
            return (
              <li
                key={`${r.lat}-${r.lng}-${i}`}
                id={`${id}-option-${i}`}
                className={`autocomplete-option${i === activeIndex ? " active" : ""}`}
                role="option"
                aria-selected={i === activeIndex}
                onMouseDown={(e) => e.preventDefault()} // prevent input blur before click fires
                onClick={() => selectResult(r)}
              >
                <span className="autocomplete-option-icon">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M21 10c0 7-9 13-9 13S3 17 3 10a9 9 0 0 1 18 0z" /><circle cx="12" cy="10" r="3" />
                  </svg>
                </span>
                <span className="autocomplete-option-text">
                  <span className="autocomplete-option-primary">{primary}</span>
                  {rest.length > 0 && (
                    <span className="autocomplete-option-secondary">{rest.join(", ")}</span>
                  )}
                </span>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
