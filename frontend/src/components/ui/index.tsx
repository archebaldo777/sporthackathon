import clsx from "clsx";
import { Check, ChevronDown, Loader2, X } from "lucide-react";
import { createContext, forwardRef, useContext, useEffect, useId, type AriaAttributes, useMemo, useRef, useState, type ButtonHTMLAttributes, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes, type TextareaHTMLAttributes } from "react";

/* ------------------------------------------------------------------ Button */
type BtnProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost" | "danger" | "dark" | "outline";
  size?: "sm" | "md" | "lg";
  loading?: boolean;
  icon?: ReactNode;
};
export const Button = forwardRef<HTMLButtonElement, BtnProps>(function Button(
  { variant = "primary", size = "md", loading, icon, className, children, disabled, ...rest }, ref) {
  return (
    <button
      ref={ref}
      disabled={disabled || loading}
      className={clsx(
        "inline-flex items-center justify-center gap-2 rounded-xl font-medium transition active:translate-y-px disabled:opacity-50 disabled:pointer-events-none whitespace-nowrap",
        size === "sm" && "h-8 px-3 text-[13px]",
        size === "md" && "h-10 px-4 text-[14px]",
        size === "lg" && "h-12 px-6 text-[15px]",
        variant === "primary" && "bg-brand-500 text-white hover:bg-brand-600 shadow-[0_6px_18px_-8px_rgba(64,47,255,.7)]",
        variant === "secondary" && "bg-brand-50 text-brand-700 hover:bg-brand-100",
        variant === "outline" && "border border-line bg-white text-ink hover:border-brand-300 hover:text-brand-700",
        variant === "ghost" && "text-ink-2 hover:bg-surface hover:text-ink",
        variant === "danger" && "bg-accent-50 text-accent-700 hover:bg-accent-100",
        variant === "dark" && "bg-night text-white hover:bg-night-3",
        className,
      )}
      {...rest}
    >
      {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : icon}
      {children}
    </button>
  );
});

/* ------------------------------------------------------------------ Card */
export function Card({ className, children, ...rest }: { className?: string; children: ReactNode } & React.HTMLAttributes<HTMLDivElement>) {
  return <div className={clsx("card", className)} {...rest}>{children}</div>;
}
export function CardHeader({ title, subtitle, action, icon }: { title: ReactNode; subtitle?: ReactNode; action?: ReactNode; icon?: ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-4 px-5 pt-5 pb-3">
      <div className="flex items-start gap-3 min-w-0">
        {icon && <div className="mt-0.5 grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-brand-50 text-brand-600">{icon}</div>}
        <div className="min-w-0">
          <h3 className="text-[15px] font-semibold text-ink leading-tight">{title}</h3>
          {subtitle && <p className="mt-1 text-[13px] text-ink-3 leading-snug">{subtitle}</p>}
        </div>
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  );
}

/* ------------------------------------------------------------------ Badge */
export type Tone = "brand" | "ok" | "warn" | "danger" | "neutral" | "dark" | "fsp";
export function Badge({ tone = "neutral", children, className, icon }: { tone?: Tone; children: ReactNode; className?: string; icon?: ReactNode }) {
  return (
    <span className={clsx(
      "inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[12px] font-medium leading-5 whitespace-nowrap",
      tone === "brand" && "bg-brand-50 text-brand-700",
      tone === "ok" && "bg-ok-50 text-ok-700",
      tone === "warn" && "bg-warn-50 text-warn-700",
      tone === "danger" && "bg-accent-50 text-accent-700",
      tone === "neutral" && "bg-surface text-ink-2",
      tone === "dark" && "bg-night text-white",
      tone === "fsp" && "bg-gradient-to-r from-brand-500 to-accent-500 text-white",
      className,
    )}>{icon}{children}</span>
  );
}

/* ------------------------------------------------------------------ Form controls */
// Field связывает подпись, подсказку и ошибку с полем ввода (for/id, aria-describedby, aria-invalid) — для скринридеров
const FieldCtx = createContext<{ id: string; describedBy?: string; invalid?: boolean } | null>(null);
function useFieldProps<T extends { id?: string; "aria-describedby"?: string; "aria-invalid"?: AriaAttributes["aria-invalid"] }>(rest: T): T {
  const f = useContext(FieldCtx);
  if (!f) return rest;
  return { ...rest, id: rest.id ?? f.id, "aria-describedby": rest["aria-describedby"] ?? f.describedBy, "aria-invalid": rest["aria-invalid"] ?? (f.invalid || undefined) };
}
export function Field({ label, hint, error, children, className, required }: { label?: ReactNode; hint?: ReactNode; error?: string | null; children: ReactNode; className?: string; required?: boolean }) {
  const id = useId();
  const noteId = error || hint ? `${id}-note` : undefined;
  return (
    <FieldCtx.Provider value={{ id, describedBy: noteId, invalid: !!error }}>
      <div className={className}>
        {label && <label className="label" htmlFor={id}>{label}{required && <span className="text-accent-500"> *</span>}</label>}
        {children}
        {error ? <p id={noteId} className="mt-1 text-xs text-accent-600">{error}</p> : hint ? <p id={noteId} className="hint">{hint}</p> : null}
      </div>
    </FieldCtx.Provider>
  );
}
export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(function Input({ className, ...rest }, ref) {
  return <input ref={ref} className={clsx("input", className)} {...useFieldProps(rest)} />;
});
export const Textarea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement>>(function Textarea({ className, ...rest }, ref) {
  return <textarea ref={ref} className={clsx("input min-h-[96px] resize-y leading-relaxed", className)} {...useFieldProps(rest)} />;
});
export function Select({ className, children, ...rest }: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <div className="relative">
      <select className={clsx("input appearance-none pr-9", className)} {...useFieldProps(rest)}>{children}</select>
      <ChevronDown className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-3" />
    </div>
  );
}
export function Checkbox({ checked, onChange, label, description, disabled }: { checked: boolean; onChange: (v: boolean) => void; label: ReactNode; description?: ReactNode; disabled?: boolean }) {
  const id = useId();
  return (
    <label htmlFor={id} className={clsx("flex cursor-pointer items-start gap-3 select-none", disabled && "opacity-60 cursor-not-allowed")}>
      <span className={clsx("mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-md border transition", checked ? "border-brand-500 bg-brand-500" : "border-ink-4 bg-white")}>
        {checked && <Check className="h-3.5 w-3.5 text-white" strokeWidth={3} />}
      </span>
      <input id={id} type="checkbox" className="sr-only" checked={checked} disabled={disabled} onChange={(e) => onChange(e.target.checked)} />
      <span className="text-[14px] leading-snug text-ink-2">{label}{description && <span className="mt-0.5 block text-xs text-ink-3">{description}</span>}</span>
    </label>
  );
}
export function Toggle({ checked, onChange, label, description }: { checked: boolean; onChange: (v: boolean) => void; label: ReactNode; description?: ReactNode }) {
  return (
    <button type="button" role="switch" aria-checked={checked} onClick={() => onChange(!checked)} className="flex w-full items-start justify-between gap-4 text-left">
      <span><span className="block text-[14px] font-medium text-ink">{label}</span>{description && <span className="mt-0.5 block text-[13px] text-ink-3">{description}</span>}</span>
      <span className={clsx("relative mt-0.5 h-6 w-11 shrink-0 rounded-full transition", checked ? "bg-brand-500" : "bg-ink-4/50")}>
        <span className={clsx("absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition", checked ? "left-[22px]" : "left-0.5")} />
      </span>
    </button>
  );
}

/* Выбор одного/нескольких значений «чипами» */
export function ChoiceChips<T extends string>({ options, value, onChange, multi }: { options: { code: T; name: string }[]; value: T[] | T | null; onChange: (v: any) => void; multi?: boolean }) {
  const arr = Array.isArray(value) ? value : value ? [value] : [];
  return (
    <div className="flex flex-wrap gap-2">
      {options.map((o) => {
        const on = arr.includes(o.code);
        return (
          <button key={o.code} type="button"
            onClick={() => (multi ? onChange(on ? arr.filter((x) => x !== o.code) : [...arr, o.code]) : onChange(o.code))}
            className={clsx("rounded-xl border px-3 py-1.5 text-[13px] font-medium transition",
              on ? "border-brand-500 bg-brand-500 text-white shadow-lift" : "border-line bg-white text-ink-2 hover:border-brand-300")}>
            {o.name}
          </button>
        );
      })}
    </div>
  );
}

/* Ввод тегов-навыков с подсказками из онтологии */
export function TagInput({ value, onChange, suggestions = [], placeholder, max = 30 }: { value: string[]; onChange: (v: string[]) => void; suggestions?: string[]; placeholder?: string; max?: number }) {
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const list = useMemo(() => {
    const ql = q.trim().toLowerCase();
    return Array.from(new Set(suggestions)).filter((s) => !value.includes(s) && (!ql || s.toLowerCase().includes(ql))).slice(0, 8);
  }, [q, suggestions, value]);
  useEffect(() => {
    const h = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false); };
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, []);
  const add = (s: string) => {
    const t = s.trim();
    if (t && !value.includes(t) && value.length < max) onChange([...value, t]);
    setQ("");
  };
  return (
    <div ref={ref} className="relative">
      <div className="input flex min-h-[46px] flex-wrap items-center gap-1.5 py-1.5" onClick={() => setOpen(true)}>
        {value.map((s) => (
          <span key={s} className="inline-flex items-center gap-1 rounded-lg bg-brand-50 px-2 py-1 text-[13px] font-medium text-brand-700">
            {s}
            <button type="button" aria-label={`Удалить ${s}`} onClick={(e) => { e.stopPropagation(); onChange(value.filter((x) => x !== s)); }} className="text-brand-400 hover:text-brand-700"><X className="h-3.5 w-3.5" /></button>
          </span>
        ))}
        <input value={q} onChange={(e) => { setQ(e.target.value); setOpen(true); }} onFocus={() => setOpen(true)}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === ",") { e.preventDefault(); if (list[0] && q) add(list[0]); else if (q) add(q); }
            if (e.key === "Backspace" && !q && value.length) onChange(value.slice(0, -1));
          }}
          placeholder={value.length ? "" : placeholder} className="min-w-[120px] flex-1 border-0 bg-transparent p-1 text-[14px] outline-none" />
      </div>
      {open && list.length > 0 && (
        <div className="absolute z-30 mt-1 max-h-64 w-full overflow-auto rounded-xl border border-line bg-white p-1 shadow-lg">
          {list.map((s) => (
            <button key={s} type="button" onClick={() => add(s)} className="block w-full rounded-lg px-3 py-2 text-left text-[14px] hover:bg-brand-50">{s}</button>
          ))}
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ Tabs */
export function Tabs<T extends string>({ tabs, value, onChange, className }: { tabs: { id: T; label: ReactNode; count?: number }[]; value: T; onChange: (v: T) => void; className?: string }) {
  return (
    <div className={clsx("flex gap-1 overflow-x-auto scrollbar-thin rounded-xl bg-surface p-1", className)} role="tablist">
      {tabs.map((t) => (
        <button key={t.id} role="tab" aria-selected={value === t.id} onClick={() => onChange(t.id)}
          className={clsx("flex items-center gap-2 whitespace-nowrap rounded-lg px-3.5 py-2 text-[13px] font-medium transition",
            value === t.id ? "bg-white text-ink shadow-card" : "text-ink-3 hover:text-ink")}>
          {t.label}
          {t.count != null && <span className={clsx("rounded-full px-1.5 text-[11px] num", value === t.id ? "bg-brand-50 text-brand-700" : "bg-white/70")}>{t.count}</span>}
        </button>
      ))}
    </div>
  );
}

/* ------------------------------------------------------------------ Modal */
export function Modal({ open, onClose, title, children, footer, wide }: { open: boolean; onClose: () => void; title: ReactNode; children: ReactNode; footer?: ReactNode; wide?: boolean }) {
  useEffect(() => {
    if (!open) return;
    const h = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", h);
    document.body.style.overflow = "hidden";
    return () => { document.removeEventListener("keydown", h); document.body.style.overflow = ""; };
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-night/50 p-0 backdrop-blur-[2px] sm:items-center sm:p-6" onMouseDown={onClose}>
      <div role="dialog" aria-modal="true" onMouseDown={(e) => e.stopPropagation()}
        className={clsx("animate-fade-in flex max-h-[92vh] w-full flex-col rounded-t-2xl bg-white shadow-2xl sm:rounded-2xl", wide ? "sm:max-w-3xl" : "sm:max-w-lg")}>
        <div className="flex items-center justify-between gap-4 border-b border-line px-5 py-4">
          <h3 className="text-[16px] font-semibold">{title}</h3>
          <button onClick={onClose} aria-label="Закрыть" className="rounded-lg p-1.5 text-ink-3 hover:bg-surface hover:text-ink"><X className="h-5 w-5" /></button>
        </div>
        <div className="overflow-y-auto px-5 py-4">{children}</div>
        {footer && <div className="flex flex-wrap justify-end gap-2 border-t border-line px-5 py-3.5">{footer}</div>}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ Feedback */
export function Spinner({ className }: { className?: string }) {
  return <Loader2 className={clsx("h-5 w-5 animate-spin text-brand-500", className)} />;
}
export function Skeleton({ className }: { className?: string }) {
  return <div className={clsx("animate-pulse rounded-xl bg-line/70", className)} />;
}
export function PageLoader() {
  return <div className="grid min-h-[40vh] place-items-center"><Spinner className="h-7 w-7" /></div>;
}
export function EmptyState({ icon, title, text, action }: { icon?: ReactNode; title: ReactNode; text?: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center px-6 py-12 text-center">
      {icon && <div className="mb-4 grid h-12 w-12 place-items-center rounded-2xl bg-brand-50 text-brand-500">{icon}</div>}
      <h3 className="text-[15px] font-semibold">{title}</h3>
      {text && <p className="mt-1.5 max-w-md text-[14px] text-ink-3">{text}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}
export function Alert({ tone = "brand", title, children, icon }: { tone?: "brand" | "warn" | "danger" | "ok"; title?: ReactNode; children?: ReactNode; icon?: ReactNode }) {
  return (
    <div className={clsx("flex gap-3 rounded-xl border px-4 py-3 text-[14px]",
      tone === "brand" && "border-brand-100 bg-brand-50/60 text-brand-900",
      tone === "warn" && "border-warn-500/20 bg-warn-50 text-warn-700",
      tone === "danger" && "border-accent-100 bg-accent-50 text-accent-700",
      tone === "ok" && "border-ok-500/20 bg-ok-50 text-ok-700")}>
      {icon && <div className="mt-0.5 shrink-0">{icon}</div>}
      <div className="min-w-0">{title && <div className="font-semibold">{title}</div>}{children && <div className={clsx(title && "mt-0.5", "opacity-90")}>{children}</div>}</div>
    </div>
  );
}

/* ------------------------------------------------------------------ Data display */
export function Stat({ label, value, hint, accent }: { label: ReactNode; value: ReactNode; hint?: ReactNode; accent?: boolean }) {
  return (
    <div className={clsx("rounded-2xl border p-4", accent ? "border-transparent bg-night text-white" : "border-line bg-white")}>
      <div className={clsx("kicker", accent && "text-white/60")}>{label}</div>
      <div className="mt-2 font-mono text-[26px] font-bold leading-none tabular-nums">{value}</div>
      {hint && <div className={clsx("mt-2 text-[12px]", accent ? "text-white/60" : "text-ink-3")}>{hint}</div>}
    </div>
  );
}
export function Meter({ value, className, tone = "brand" }: { value: number; className?: string; tone?: "brand" | "ok" | "warn" | "danger" }) {
  return (
    <div className={clsx("h-2 w-full overflow-hidden rounded-full bg-line", className)}>
      <div className={clsx("h-full rounded-full transition-all", tone === "brand" && "bg-brand-500", tone === "ok" && "bg-ok-500", tone === "warn" && "bg-warn-500", tone === "danger" && "bg-accent-500")}
        style={{ width: `${Math.max(2, Math.min(100, value * 100))}%` }} />
    </div>
  );
}
export function ScoreRing({ value, size = 56, label }: { value: number; size?: number; label?: string }) {
  const r = (size - 8) / 2, c = 2 * Math.PI * r, v = Math.max(0, Math.min(100, value));
  const color = v >= 72 ? "#402FFF" : v >= 58 ? "#7A68FF" : "#9B9C9E";
  return (
    <div className="relative shrink-0" style={{ width: size, height: size }} title={label}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} stroke="#DCDCE0" strokeWidth={6} fill="none" />
        <circle cx={size / 2} cy={size / 2} r={r} stroke={color} strokeWidth={6} fill="none" strokeLinecap="round" strokeDasharray={c} strokeDashoffset={c * (1 - v / 100)} />
      </svg>
      <div className="absolute inset-0 grid place-items-center font-mono text-[15px] font-bold tabular-nums">{Math.round(v)}</div>
    </div>
  );
}
export function CompanyMark({ name, accent, size = 40 }: { name: string; accent?: string | null; size?: number }) {
  const letters = name.replace(/[«»"]/g, "").split(/\s+/).map((w) => w[0]).join("").slice(0, 2).toUpperCase();
  return (
    <div className="grid shrink-0 place-items-center rounded-xl font-mono font-bold text-white" style={{ width: size, height: size, background: accent || "#402FFF", fontSize: size * 0.36 }}>
      {letters}
    </div>
  );
}
/** Логотип «Драфт» по правилам брендбука ФСП для проектов Федерации: собственный словесный знак акцентным шрифтом ФСП
 *  (TDAText) и официальный логотип ФСП через разделитель — без изменения самого логотипа ФСП. */
export function Logo({ dark, compact, fsp = true }: { dark?: boolean; compact?: boolean; fsp?: boolean }) {
  return (
    <div className="flex items-center gap-3">
      <div className="leading-none">
        <div className={clsx("font-pixel tracking-[0.06em]", compact ? "text-[18px]" : "text-[21px]", dark ? "text-white" : "text-ink")}>
          ДРАФТ<span className="text-accent-500">_</span>
        </div>
        {!compact && <div className={clsx("mt-1 font-mono text-[9.5px] uppercase tracking-[0.14em]", dark ? "text-white/50" : "text-ink-3")}>ИТ-найм</div>}
      </div>
      {fsp && !compact && (
        <>
          <span className={clsx("h-7 w-px", dark ? "bg-white/20" : "bg-line")} aria-hidden />
          <FspLogo dark={dark} className="h-6" />
        </>
      )}
    </div>
  );
}

/** Официальный логотип ФСП (файлы брендбука): short — знак и «ФСП», full — с полным названием, star — только знак. */
export function FspLogo({ dark, variant = "short", className }: { dark?: boolean; variant?: "short" | "full" | "star"; className?: string }) {
  return <img src={`/brand/fsp-${variant}-${dark ? "dark" : "light"}.svg`} alt="Федерация спортивного программирования России" className={clsx("w-auto", className)} />;
}

/** Гибридный паттерн ФСП — полоса символов кода (графический элемент брендбука). */
export function PatternStrip({ light, className }: { light?: boolean; className?: string }) {
  return <div aria-hidden className={clsx(light ? "pattern-strip-light" : "pattern-strip", "h-6", className)} />;
}

/* Мини-разметка для текстов заданий: `код`, **жирный**, ``` блоки, переносы строк */
export function RichText({ text, className }: { text: string; className?: string }) {
  const blocks = text.split(/```/);
  return (
    <div className={clsx("space-y-2 text-[15px] leading-relaxed", className)}>
      {blocks.map((b, i) =>
        i % 2 === 1 ? <pre key={i} className="code-block">{b.replace(/^\w*\n/, "")}</pre> : (
          b.split(/\n\n+/).filter(Boolean).map((para, j) => (
            <p key={`${i}-${j}`} className="whitespace-pre-line">
              {para.split(/(`[^`]+`|\*\*[^*]+\*\*)/).map((t, k) =>
                t.startsWith("`") ? <code key={k} className="rounded-md bg-brand-50 px-1.5 py-0.5 font-mono text-[13px] text-brand-800">{t.slice(1, -1)}</code>
                  : t.startsWith("**") ? <strong key={k}>{t.slice(2, -2)}</strong> : <span key={k}>{t}</span>)}
            </p>
          ))
        ))}
    </div>
  );
}

export function DataTable({ name, columns, rows }: { name?: string; columns: string[]; rows: (string | number | null)[][] }) {
  return (
    <div className="overflow-hidden rounded-xl border border-line">
      {name && <div className="border-b border-line bg-surface px-3 py-1.5 font-mono text-[12px] font-semibold text-ink-2">{name}</div>}
      <div className="overflow-x-auto scrollbar-thin">
        <table className="w-full text-[13px]">
          <thead><tr>{columns.map((c) => <th key={c} className="whitespace-nowrap border-b border-line bg-white px-3 py-2 text-left font-mono font-semibold text-ink-2">{c}</th>)}</tr></thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i} className="odd:bg-surface/50">
                {r.map((v, j) => <td key={j} className="whitespace-nowrap px-3 py-1.5 font-mono text-ink">{v === null ? <span className="text-ink-4">NULL</span> : String(v)}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function SectionTitle({ kicker, title, text, action }: { kicker?: string; title: ReactNode; text?: ReactNode; action?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        {kicker && <div className="kicker mb-2">{kicker}</div>}
        <h1 className="text-[26px] font-bold leading-tight sm:text-[30px]">{title}</h1>
        {text && <p className="mt-2 max-w-2xl text-[15px] text-ink-3">{text}</p>}
      </div>
      {action}
    </div>
  );
}
