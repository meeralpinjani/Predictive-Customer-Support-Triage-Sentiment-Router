import { useEffect, useRef, useState } from "react";
import { Link, Navigate, useNavigate, useSearchParams } from "react-router-dom";
import clsx from "clsx";
import {
  AlertCircle, ArrowLeft, ArrowRight, BarChart3, Check, Eye, EyeOff, Info, Loader2, Lock, Mail, Moon, Route, Snowflake,
  Sun, User, Zap,
} from "lucide-react";
import { api } from "../../api.js";
import { useAuth } from "../../lib/auth.jsx";
import { homeFor } from "../../lib/meta.js";
import { useTheme } from "../../components/ui.jsx";

const PLANS = [
  { id: "free", name: "Free", note: "8h response target" },
  { id: "basic", name: "Basic", note: "4h response target" },
  { id: "pro", name: "Pro", note: "2h response target" },
  { id: "enterprise", name: "Enterprise", note: "1h response target" },
];

export const PASSWORD_RULES = [
  { label: "At least 8 characters", test: (p) => p.length >= 8 },
  { label: "One uppercase letter", test: (p) => /[A-Z]/.test(p) },
  { label: "One lowercase letter", test: (p) => /[a-z]/.test(p) },
  { label: "One number", test: (p) => /[0-9]/.test(p) },
];
const passwordOk = (p) => PASSWORD_RULES.every((r) => r.test(p));

// ------------------------------------------------------------------ layout
function Brand({ small }) {
  return (
    <div className="flex items-center gap-3">
      <span className={clsx("rounded-2xl bg-fjord grid place-items-center", small ? "w-9 h-9" : "w-10 h-10")}>
        <Snowflake className="w-5 h-5 text-sky-300" aria-hidden />
      </span>
      <span>
        <span className="block font-extrabold tracking-tight leading-tight">Support Triage Router</span>
        <span className="block text-[11px] text-ink-3">Triage &amp; routing · AlgoAmigos</span>
      </span>
    </div>
  );
}

/** The routing story in one picture: priority cards flow to the three support levels. */
function RoutingIllustration() {
  const tickets = [
    { label: "Critical", color: "bg-senior", soft: "bg-senior-soft", text: "text-senior-text" },
    { label: "Technical", color: "bg-tier2", soft: "bg-tier2-soft", text: "text-tier2-text" },
    { label: "Routine", color: "bg-tier1", soft: "bg-tier1-soft", text: "text-tier1-text" },
  ];
  const teams = [
    { name: "Expert Escalation", sub: "Level 3 · critical issues", initials: "ME", color: "bg-senior" },
    { name: "Technical Support", sub: "Level 2 · technical issues", initials: "IB", color: "bg-tier2" },
    { name: "General Support", sub: "Level 1 · common questions", initials: "AL", color: "bg-tier1" },
  ];
  return (
    <div className="relative mt-10 grid grid-cols-[1fr_auto_1.2fr] items-center gap-3 max-w-lg" aria-hidden>
      <div className="space-y-3">
        {tickets.map((t) => (
          <div key={t.label} className="rounded-2xl bg-card/90 border border-line p-3 shadow-sm">
            <div className="flex items-center gap-2">
              <span className={clsx("w-2 h-2 rounded-full", t.color)} />
              <span className={clsx("text-[11px] font-bold", t.text)}>{t.label}</span>
            </div>
            <div className={clsx("mt-2 h-1.5 rounded-full w-4/5", t.soft)} />
            <div className="mt-1.5 h-1.5 rounded-full w-3/5 bg-sunken" />
          </div>
        ))}
      </div>
      <div className="flex flex-col gap-[52px] text-glacier">
        {[0, 1, 2].map((i) => <ArrowRight key={i} className="w-5 h-5" />)}
      </div>
      <div className="space-y-3">
        {teams.map((t) => (
          <div key={t.name} className="rounded-2xl bg-card border border-line p-3 shadow-sm flex items-center gap-3">
            <span className={clsx("w-9 h-9 rounded-full grid place-items-center text-white text-xs font-bold", t.color)}>{t.initials}</span>
            <span className="min-w-0">
              <span className="block text-xs font-bold truncate">{t.name}</span>
              <span className="block text-[10px] text-ink-3 truncate">{t.sub}</span>
            </span>
          </div>
        ))}
      </div>
      <p className="col-span-3 mt-3 text-right text-ink-3 -rotate-2 font-hand text-xl leading-tight">
        Right ticket · right team · faster resolution ↗
      </p>
    </div>
  );
}

function AuthLayout({ children }) {
  const [theme, toggleTheme] = useTheme();
  return (
    <div className="min-h-screen grid lg:grid-cols-[1.15fr_1fr] bg-canvas">
      <aside className="hidden lg:flex flex-col justify-between p-12 xl:p-16 bg-gradient-to-br from-glacier-soft via-canvas to-canvas border-r border-line">
        <Brand />
        <div>
          <p className="eyebrow !text-glacier-text">Smarter support · happier customers</p>
          <h1 className="mt-3 text-4xl xl:text-5xl font-extrabold tracking-tight leading-[1.1]">
            AI-powered support triage <br />for <span className="text-glacier">faster resolutions</span>
          </h1>
          <p className="mt-4 max-w-md text-ink-2">
            Every ticket is read for frustration, urgency and customer value, scored, and routed to the right level, live.
          </p>
          <ul className="mt-8 space-y-4">
            {[
              [Zap, "AI-driven prioritisation", "Urgent and frustrated customers first"],
              [Route, "Smarter routing", "General, Technical or Expert, automatically"],
              [BarChart3, "Measured impact", "Every decision explained, every number real"],
            ].map(([Icon, t, s]) => (
              <li key={t} className="flex items-center gap-3">
                <span className="w-10 h-10 rounded-2xl bg-card border border-line grid place-items-center"><Icon className="w-4 h-4 text-glacier" aria-hidden /></span>
                <span><span className="block font-semibold text-sm">{t}</span><span className="block text-xs text-ink-3">{s}</span></span>
              </li>
            ))}
          </ul>
          <RoutingIllustration />
        </div>
        <p className="text-xs text-ink-3">HelloWorld KIT ’26</p>
      </aside>
      <main className="relative flex items-center justify-center p-5 sm:p-10">
        <button onClick={toggleTheme} className="absolute top-5 right-5 btn-ghost !p-2 !rounded-full" aria-label="Toggle theme">
          {theme === "dark" ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
        </button>
        <div className="w-full max-w-[420px]">
          <div className="lg:hidden mb-8"><Brand small /></div>
          <div className="tile !p-7 sm:!p-8">{children}</div>
        </div>
      </main>
    </div>
  );
}

function Heading({ title, subtitle }) {
  return (
    <div className="mb-6">
      <h2 className="text-2xl font-extrabold tracking-tight">{title}</h2>
      {subtitle && <p className="mt-1 text-sm text-ink-3">{subtitle}</p>}
    </div>
  );
}

/** Input with a leading icon and a small floating label, as in the mockup. */
function IconField({ icon: Icon, label, type = "text", value, onChange, autoComplete, required = true, minLength, toggle }) {
  const [show, setShow] = useState(false);
  const actualType = toggle ? (show ? "text" : "password") : type;
  return (
    <label className="flex items-center gap-3 rounded-2xl border border-line bg-sunken px-3.5 py-2 focus-within:ring-2 focus-within:ring-glacier/30 focus-within:border-glacier transition">
      <Icon className="w-4 h-4 text-ink-3 shrink-0" aria-hidden />
      <span className="flex-1 min-w-0">
        <span className="block text-[11px] text-ink-3">{label}</span>
        <input aria-label={label} className="w-full bg-transparent text-sm text-ink outline-none placeholder:text-ink-3" type={actualType} value={value}
               onChange={(e) => onChange(e.target.value)} autoComplete={autoComplete} required={required} minLength={minLength} />
      </span>
      {toggle && (
        <button type="button" onClick={() => setShow((s) => !s)} className="text-ink-3 hover:text-ink" aria-label={show ? "Hide password" : "Show password"}>
          {show ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
        </button>
      )}
    </label>
  );
}

function Alert({ kind = "error", title, children }) {
  return (
    <div role="alert" className={clsx("flex gap-3 rounded-2xl border p-3.5 text-sm",
      kind === "error" ? "border-senior/30 bg-senior-soft/60" : "border-glacier/30 bg-glacier-soft/60")}>
      {kind === "error" ? <AlertCircle className="w-5 h-5 text-senior-text shrink-0" aria-hidden /> : <Info className="w-5 h-5 text-glacier-text shrink-0" aria-hidden />}
      <div>
        {title && <p className={clsx("font-semibold", kind === "error" ? "text-senior-text" : "text-glacier-text")}>{title}</p>}
        <div className="text-ink-2">{children}</div>
      </div>
    </div>
  );
}

function PrimaryButton({ busy, children, disabled }) {
  return (
    <button className="btn-primary w-full !py-3" disabled={busy || disabled}>
      {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : null}{children}{!busy && <ArrowRight className="w-4 h-4" />}
    </button>
  );
}

function PasswordChecklist({ password }) {
  return (
    <ul className="grid grid-cols-2 gap-x-3 gap-y-1">
      {PASSWORD_RULES.map((r) => {
        const ok = r.test(password);
        return (
          <li key={r.label} className={clsx("flex items-center gap-1.5 text-xs", ok ? "text-tier1-text" : "text-ink-3")}>
            <span className={clsx("w-4 h-4 rounded-full grid place-items-center", ok ? "bg-tier1 text-white" : "bg-sunken")}>
              {ok && <Check className="w-3 h-3" />}
            </span>{r.label}
          </li>
        );
      })}
    </ul>
  );
}

let googleInitFor = null;
const googleHandler = { current: null };

/** Official "Sign in with Google" button (Google Identity Services). Hidden until configured. */
function GoogleButton({ onError }) {
  const { googleClientId, google } = useAuth();
  const navigate = useNavigate();
  const ref = useRef();
  const [theme] = useTheme();

  // Google allows one initialize() per page; route its callback to whichever button is mounted now.
  googleHandler.current = async ({ credential }) => {
    try {
      const u = await google(credential);
      navigate(u.profile_complete ? homeFor(u) : "/welcome", { replace: true });
    } catch (err) {
      onError(err.message);
    }
  };

  useEffect(() => {
    if (!googleClientId || !ref.current) return;
    const render = () => {
      if (googleInitFor !== googleClientId) {
        window.google.accounts.id.initialize({ client_id: googleClientId, callback: (r) => googleHandler.current?.(r) });
        googleInitFor = googleClientId;
      }
      if (!ref.current) return;
      ref.current.innerHTML = "";
      window.google.accounts.id.renderButton(ref.current, {
        theme: theme === "dark" ? "filled_black" : "outline", size: "large", width: 340, text: "continue_with", shape: "pill",
      });
    };
    if (window.google?.accounts?.id) return render();
    const s = document.createElement("script");
    s.src = "https://accounts.google.com/gsi/client";
    s.async = true;
    s.onload = render;
    s.onerror = () => onError("Could not load Google sign-in. Check your connection.");
    document.head.appendChild(s);
  }, [googleClientId, theme]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!googleClientId) return null;
  return (
    <>
      <div className="my-5 flex items-center gap-3 text-xs text-ink-3"><span className="h-px flex-1 bg-line" />OR<span className="h-px flex-1 bg-line" /></div>
      <div className="flex justify-center" ref={ref} />
    </>
  );
}

/** Shows a one-time recovery code with copy / download and an "I saved it" confirmation. */
export function RecoveryCodeCard({ code, email, onDone, doneLabel = "Continue" }) {
  const [saved, setSaved] = useState(false);
  const [copied, setCopied] = useState(false);
  const download = () => {
    const blob = new Blob([
      `Support Triage Router - account recovery code\n\nAccount: ${email}\nRecovery code: ${code}\n\n` +
      "Use it on the sign-in page under 'Forgot password?'. It works once; you get a new one after using it.\n",
    ], { type: "text/plain" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "triage-router-recovery-code.txt";
    a.click();
    URL.revokeObjectURL(a.href);
  };
  return (
    <div className="space-y-4">
      <Alert kind="info" title="Save your recovery code">
        If you ever forget your password, this code lets you reset it yourself. It's shown only now.
      </Alert>
      <div className="rounded-2xl border-2 border-dashed border-glacier/50 bg-glacier-soft/40 py-5 text-center">
        <p className="font-mono text-2xl font-bold tracking-[0.2em] select-all" aria-label="Recovery code">{code}</p>
      </div>
      <div className="grid grid-cols-2 gap-2">
        <button type="button" className="btn-ghost" onClick={async () => {
          try {
            await navigator.clipboard.writeText(code);
            setCopied(true);
          } catch {
            /* clipboard blocked: the code is selectable */
          }
        }}>{copied ? <><Check className="w-4 h-4" />Copied</> : "Copy"}</button>
        <button type="button" className="btn-ghost" onClick={download}>Download .txt</button>
      </div>
      <label className="flex items-center gap-2 text-sm cursor-pointer select-none">
        <input type="checkbox" checked={saved} onChange={(e) => setSaved(e.target.checked)} className="w-4 h-4 accent-[rgb(var(--glacier))]" />
        I've saved my recovery code somewhere safe
      </label>
      <button type="button" className="btn-primary w-full !py-3" disabled={!saved} onClick={onDone}>
        {doneLabel}<ArrowRight className="w-4 h-4" />
      </button>
    </div>
  );
}

// ------------------------------------------------------------------ pages
export function LoginPage() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [remember, setRemember] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  if (user) return <Navigate to={homeFor(user)} replace />;

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await login(email, password, remember);
      navigate("/", { replace: true });
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthLayout>
      <Heading title="Welcome back" subtitle="Sign in to your account" />
      <form onSubmit={submit} className="space-y-3">
        {error && (
          <Alert title={error.startsWith("Wrong") ? "We couldn't sign you in" : "Something went wrong"}>
            {error.startsWith("Wrong") ? "That email and password don't match an account. Check them and try again." : error}
          </Alert>
        )}
        <IconField icon={Mail} label="Email address" type="email" autoComplete="email" value={email} onChange={setEmail} />
        <IconField icon={Lock} label="Password" toggle autoComplete="current-password" value={password} onChange={setPassword} />
        <div className="flex items-center justify-between text-sm pt-1">
          <label className="flex items-center gap-2 cursor-pointer select-none">
            <input type="checkbox" checked={remember} onChange={(e) => setRemember(e.target.checked)} className="w-4 h-4 accent-[rgb(var(--glacier))]" />
            Remember me
          </label>
          <Link to="/forgot-password" className="font-semibold text-glacier-text hover:underline">Forgot password?</Link>
        </div>
        <PrimaryButton busy={busy}>Sign in</PrimaryButton>
      </form>
      <GoogleButton onError={setError} />
      <p className="mt-6 text-sm text-ink-3 text-center">
        New here? <Link to="/signup" className="font-semibold text-glacier-text hover:underline">Create an account</Link>
      </p>
    </AuthLayout>
  );
}

function PlanPicker({ value, onChange }) {
  return (
    <fieldset>
      <legend className="eyebrow mb-1.5">Your plan</legend>
      <div className="grid grid-cols-2 gap-2">
        {PLANS.map((p) => (
          <label key={p.id} className={clsx("cursor-pointer rounded-2xl border p-3 transition",
            value === p.id ? "border-glacier bg-glacier-soft/60 ring-2 ring-glacier/15" : "border-line hover:border-ink-3/40")}>
            <input type="radio" name="plan" value={p.id} checked={value === p.id} onChange={() => onChange(p.id)} className="sr-only" />
            <span className="block text-sm font-semibold">{p.name}</span>
            <span className="block text-[11px] text-ink-3">{p.note}</span>
          </label>
        ))}
      </div>
    </fieldset>
  );
}

export function SignupPage() {
  const { user, refresh } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ name: "", email: "", password: "", plan: "free" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [created, setCreated] = useState(null);
  if (user && !created) return <Navigate to={homeFor(user)} replace />;
  const set = (k) => (v) => setForm((f) => ({ ...f, [k]: v }));

  const submit = async (e) => {
    e.preventDefault();
    if (!passwordOk(form.password)) return setError("Please choose a stronger password.");
    setBusy(true);
    setError("");
    try {
      setCreated(await api.signup(form));   // signed in; show the recovery code before entering the app
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  if (created) {
    return (
      <AuthLayout>
        <Heading title={`Welcome, ${created.name.split(" ")[0]}!`} subtitle="Your account is ready. One last thing:" />
        <RecoveryCodeCard code={created.recovery_code} email={created.email} doneLabel="Go to my tickets"
                          onDone={async () => { await refresh(); navigate("/", { replace: true }); }} />
      </AuthLayout>
    );
  }

  return (
    <AuthLayout>
      <Heading title="Create your account" subtitle="Get help from the right team, fast." />
      <form onSubmit={submit} className="space-y-3">
        {error && <Alert title="Couldn't create the account">{error}</Alert>}
        <IconField icon={User} label="Full name" autoComplete="name" value={form.name} onChange={set("name")} />
        <IconField icon={Mail} label="Email address" type="email" autoComplete="email" value={form.email} onChange={set("email")} />
        <IconField icon={Lock} label="Password" toggle autoComplete="new-password" value={form.password} onChange={set("password")} />
        {form.password && <PasswordChecklist password={form.password} />}
        <PlanPicker value={form.plan} onChange={set("plan")} />
        <PrimaryButton busy={busy}>Create account</PrimaryButton>
      </form>
      <GoogleButton onError={setError} />
      <p className="mt-6 text-sm text-ink-3 text-center">
        Already have an account? <Link to="/login" className="font-semibold text-glacier-text hover:underline">Sign in</Link>
      </p>
    </AuthLayout>
  );
}

export function ForgotPasswordPage() {
  const navigate = useNavigate();
  const [mode, setMode] = useState("code"); // code | admin
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [newCode, setNewCode] = useState(null);
  const [requested, setRequested] = useState(null);
  const match = confirm.length > 0 && password === confirm;

  const recover = async (e) => {
    e.preventDefault();
    if (!passwordOk(password)) return setError("Please meet all the password rules.");
    if (!match) return setError("The passwords don't match.");
    setBusy(true);
    setError("");
    try {
      const res = await api.recover(email, code, password);
      setNewCode(res.recovery_code);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const askAdmin = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      setRequested(await api.forgot(email));
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  if (newCode) {
    return (
      <AuthLayout>
        <Heading title="Password changed" subtitle="Your old recovery code is used up. Here is your new one." />
        <RecoveryCodeCard code={newCode} email={email} doneLabel="Go to sign in" onDone={() => navigate("/login")} />
      </AuthLayout>
    );
  }

  return (
    <AuthLayout>
      <Link to="/login" className="inline-flex items-center gap-1 text-sm text-ink-3 hover:text-ink mb-4"><ArrowLeft className="w-4 h-4" />Back to sign in</Link>
      <Heading title="Forgot your password?"
               subtitle={mode === "code" ? "Use the recovery code you saved when you signed up." : "No code? An admin can give you a one-time reset link."} />
      <div className="grid grid-cols-2 gap-1 rounded-2xl bg-sunken p-1 mb-4" role="tablist">
        {[["code", "I have my recovery code"], ["admin", "I lost my code"]].map(([k, l]) => (
          <button key={k} type="button" role="tab" aria-selected={mode === k} onClick={() => { setMode(k); setError(""); }}
                  className={clsx("rounded-xl py-2 text-xs font-semibold transition", mode === k ? "bg-card shadow-sm text-ink" : "text-ink-3 hover:text-ink")}>
            {l}
          </button>
        ))}
      </div>

      {mode === "code" ? (
        <form onSubmit={recover} className="space-y-3">
          {error && <Alert title="Couldn't reset the password">{error}</Alert>}
          <IconField icon={Mail} label="Email address" type="email" autoComplete="email" value={email} onChange={setEmail} />
          <IconField icon={Lock} label="Recovery code (e.g. K7QX-2MPD-9RTA)" autoComplete="off" value={code} onChange={setCode} />
          <IconField icon={Lock} label="New password" toggle autoComplete="new-password" value={password} onChange={setPassword} />
          <IconField icon={Lock} label="Confirm new password" toggle autoComplete="new-password" value={confirm} onChange={setConfirm} />
          <PasswordChecklist password={password} />
          {confirm && !match && <p className="text-xs text-senior-text">Passwords don't match yet.</p>}
          <PrimaryButton busy={busy} disabled={!passwordOk(password) || !match || code.length < 8}>Reset password</PrimaryButton>
        </form>
      ) : requested ? (
        <div className="space-y-4">
          <Alert kind="info" title="Request sent">
            {requested.message} Contact your support admin; the link works once and expires in 30 minutes.
          </Alert>
          <Link to="/login" className="btn-ghost w-full">Back to sign in</Link>
        </div>
      ) : (
        <form onSubmit={askAdmin} className="space-y-3">
          {error && <Alert>{error}</Alert>}
          <IconField icon={Mail} label="Email address" type="email" autoComplete="email" value={email} onChange={setEmail} />
          <PrimaryButton busy={busy}>Ask an admin for a reset link</PrimaryButton>
          <Alert kind="info">Your request appears on the admin's Users page. They'll give you a secure, one-time link that expires in 30 minutes.</Alert>
        </form>
      )}
    </AuthLayout>
  );
}

export function ResetPasswordPage() {
  const [params] = useSearchParams();
  const token = params.get("token") || "";
  const navigate = useNavigate();
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);
  const match = confirm.length > 0 && password === confirm;

  const submit = async (e) => {
    e.preventDefault();
    if (!passwordOk(password)) return setError("Please meet all the password rules.");
    if (!match) return setError("The passwords don't match.");
    setBusy(true);
    setError("");
    try {
      await api.resetPassword(token, password);
      setDone(true);
      setTimeout(() => navigate("/login"), 2500);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthLayout>
      <Heading title="Reset your password" subtitle="Enter your new password below." />
      {!token ? (
        <Alert title="Missing link">Open the reset link your admin gave you, or <Link to="/forgot-password" className="font-semibold underline">reset with your recovery code</Link>.</Alert>
      ) : done ? (
        <Alert kind="info" title="Password changed">Taking you to sign in…</Alert>
      ) : (
        <form onSubmit={submit} className="space-y-3">
          {error && (
            <Alert title="Couldn't reset the password">
              {error} {error.includes("expired") && <Link to="/forgot-password" className="font-semibold underline">Ask for a new link</Link>}
            </Alert>
          )}
          <IconField icon={Lock} label="New password" toggle autoComplete="new-password" value={password} onChange={setPassword} />
          <IconField icon={Lock} label="Confirm new password" toggle autoComplete="new-password" value={confirm} onChange={setConfirm} />
          <PasswordChecklist password={password} />
          {confirm && !match && <p className="text-xs text-senior-text">Passwords don't match yet.</p>}
          <PrimaryButton busy={busy} disabled={!passwordOk(password) || !match}>Reset password</PrimaryButton>
        </form>
      )}
    </AuthLayout>
  );
}

/** New Google users choose their plan once. */
export function WelcomePage() {
  const { user, updateMe } = useAuth();
  const navigate = useNavigate();
  const [plan, setPlan] = useState("free");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  if (!user) return <Navigate to="/login" replace />;
  if (user.profile_complete) return <Navigate to={homeFor(user)} replace />;
  return (
    <AuthLayout>
      <Heading title={`Welcome, ${user.name.split(" ")[0]}`} subtitle="One last step: which plan are you on?" />
      <form className="space-y-4" onSubmit={async (e) => {
        e.preventDefault();
        setBusy(true);
        try {
          await updateMe({ plan });
          navigate("/", { replace: true });
        } catch (err) {
          setError(err.message);
        } finally {
          setBusy(false);
        }
      }}>
        {error && <Alert>{error}</Alert>}
        <PlanPicker value={plan} onChange={setPlan} />
        <PrimaryButton busy={busy}>Continue</PrimaryButton>
      </form>
    </AuthLayout>
  );
}
