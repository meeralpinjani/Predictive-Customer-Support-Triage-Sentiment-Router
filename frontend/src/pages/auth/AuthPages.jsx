import { useEffect, useRef, useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import clsx from "clsx";
import { Check, Loader2, Snowflake } from "lucide-react";
import { useAuth } from "../../lib/auth.jsx";
import { homeFor } from "../../lib/meta.js";
import { ErrorNote } from "../../components/ui.jsx";

const PLANS = [
  { id: "free", name: "Free", note: "8h response target" },
  { id: "basic", name: "Basic", note: "4h response target" },
  { id: "pro", name: "Pro", note: "2h response target" },
  { id: "enterprise", name: "Enterprise", note: "1h response target" },
];

function AuthFrame({ title, subtitle, children, footer }) {
  return (
    <div className="min-h-screen grid lg:grid-cols-2">
      <div className="hidden lg:flex flex-col justify-between bg-fjord text-slate-100 p-12">
        <div className="flex items-center gap-3">
          <span className="w-10 h-10 rounded-2xl bg-fjord-surface grid place-items-center"><Snowflake className="w-5 h-5 text-sky-300" aria-hidden /></span>
          <span className="font-extrabold tracking-tight text-lg">Support Triage Router</span>
        </div>
        <div>
          <p className="text-4xl font-extrabold tracking-tight leading-tight">The right person,<br />for the right ticket,<br />right now.</p>
          <ul className="mt-8 space-y-3 text-slate-300">
            {["Simple questions answered instantly", "Technical issues go straight to specialists",
              "Urgent and frustrated customers reach experts live"].map((t) => (
              <li key={t} className="flex items-center gap-3"><Check className="w-4 h-4 text-teal-300" aria-hidden />{t}</li>
            ))}
          </ul>
        </div>
        <p className="text-xs text-slate-500">AlgoAmigos · HelloWorld KIT ’26</p>
      </div>
      <div className="flex items-center justify-center p-6 sm:p-10">
        <div className="w-full max-w-sm">
          <div className="lg:hidden flex items-center gap-2 mb-8 font-extrabold tracking-tight">
            <span className="w-9 h-9 rounded-xl bg-fjord grid place-items-center"><Snowflake className="w-4 h-4 text-sky-300" aria-hidden /></span>
            Support Triage Router
          </div>
          <h1 className="text-2xl font-extrabold tracking-tight">{title}</h1>
          {subtitle && <p className="mt-1 text-sm text-ink-3">{subtitle}</p>}
          <div className="mt-6">{children}</div>
          {footer && <p className="mt-6 text-sm text-ink-3">{footer}</p>}
        </div>
      </div>
    </div>
  );
}

/** Official "Sign in with Google" button (Google Identity Services). Hidden until configured. */
function GoogleButton({ onError }) {
  const { googleClientId, google } = useAuth();
  const navigate = useNavigate();
  const ref = useRef();

  useEffect(() => {
    if (!googleClientId || !ref.current) return;
    const render = () => {
      window.google.accounts.id.initialize({
        client_id: googleClientId,
        callback: async ({ credential }) => {
          try {
            const u = await google(credential);
            navigate(u.profile_complete ? homeFor(u) : "/welcome", { replace: true });
          } catch (err) {
            onError(err.message);
          }
        },
      });
      window.google.accounts.id.renderButton(ref.current, { theme: "outline", size: "large", width: 320, text: "continue_with" });
    };
    if (window.google?.accounts?.id) return render();
    const s = document.createElement("script");
    s.src = "https://accounts.google.com/gsi/client";
    s.async = true;
    s.onload = render;
    s.onerror = () => onError("Could not load Google sign-in. Check your connection.");
    document.head.appendChild(s);
  }, [googleClientId]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!googleClientId) return null;
  return (
    <>
      <div className="flex justify-center" ref={ref} />
      <div className="my-5 flex items-center gap-3 text-xs text-ink-3"><span className="h-px flex-1 bg-line" />or<span className="h-px flex-1 bg-line" /></div>
    </>
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

export function LoginPage() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  if (user) return <Navigate to={homeFor(user)} replace />;

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await login(email, password);
      navigate("/", { replace: true });
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthFrame title="Welcome back" subtitle="Sign in to your support account."
               footer={<>New here? <Link to="/signup" className="font-semibold text-glacier-text hover:underline">Create an account</Link></>}>
      <GoogleButton onError={setError} />
      <form onSubmit={submit} className="space-y-3">
        <label className="block"><span className="eyebrow">Email</span>
          <input className="field mt-1" type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        </label>
        <label className="block"><span className="eyebrow">Password</span>
          <input className="field mt-1" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required />
        </label>
        <button className="btn-primary w-full" disabled={busy}>{busy && <Loader2 className="w-4 h-4 animate-spin" />}Sign in</button>
        {error && <ErrorNote>{error}</ErrorNote>}
      </form>
    </AuthFrame>
  );
}

export function SignupPage() {
  const { user, signup } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ name: "", email: "", password: "", plan: "free" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  if (user) return <Navigate to={homeFor(user)} replace />;
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await signup(form);
      navigate("/", { replace: true });
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthFrame title="Create your account" subtitle="Get help from the right team, fast."
               footer={<>Already have an account? <Link to="/login" className="font-semibold text-glacier-text hover:underline">Sign in</Link></>}>
      <GoogleButton onError={setError} />
      <form onSubmit={submit} className="space-y-3">
        <label className="block"><span className="eyebrow">Name</span>
          <input className="field mt-1" autoComplete="name" value={form.name} onChange={set("name")} required maxLength={80} />
        </label>
        <label className="block"><span className="eyebrow">Email</span>
          <input className="field mt-1" type="email" autoComplete="email" value={form.email} onChange={set("email")} required />
        </label>
        <label className="block"><span className="eyebrow">Password</span>
          <input className="field mt-1" type="password" autoComplete="new-password" minLength={8} value={form.password} onChange={set("password")} required />
          <span className="text-[11px] text-ink-3">At least 8 characters.</span>
        </label>
        <PlanPicker value={form.plan} onChange={(plan) => setForm((f) => ({ ...f, plan }))} />
        <button className="btn-primary w-full" disabled={busy}>{busy && <Loader2 className="w-4 h-4 animate-spin" />}Create account</button>
        {error && <ErrorNote>{error}</ErrorNote>}
      </form>
    </AuthFrame>
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
    <AuthFrame title={`Welcome, ${user.name.split(" ")[0]}`} subtitle="One last step: which plan are you on?">
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
        <PlanPicker value={plan} onChange={setPlan} />
        <button className="btn-primary w-full" disabled={busy}>{busy && <Loader2 className="w-4 h-4 animate-spin" />}Continue</button>
        {error && <ErrorNote>{error}</ErrorNote>}
      </form>
    </AuthFrame>
  );
}
