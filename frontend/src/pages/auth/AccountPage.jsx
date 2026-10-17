import { useState } from "react";
import { KeyRound, Loader2, UserRound } from "lucide-react";
import { api } from "../../api.js";
import { useAuth } from "../../lib/auth.jsx";
import { ROLE_LABEL } from "../../lib/meta.js";
import { ErrorNote, PageHeader, Tile, useToast } from "../../components/ui.jsx";
import { RecoveryCodeCard } from "./AuthPages.jsx";

export function AccountPage() {
  const { user, refresh } = useAuth();
  const toast = useToast();
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [code, setCode] = useState(null);
  const needsPassword = user.auth !== "google";

  const regenerate = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const res = await api.newRecoveryCode(password);
      setCode(res.recovery_code);
      setPassword("");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="grid gap-4 lg:grid-cols-12 pt-2">
      <PageHeader title="Account & security" subtitle="Your details and your password recovery code." />
      <Tile className="lg:col-span-5" eyebrow="Profile" icon={UserRound}>
        <dl className="space-y-3 text-sm">
          {[["Name", user.name], ["Email", user.email], ["Role", ROLE_LABEL[user.role]],
            ...(user.customer ? [["Plan", user.customer.plan]] : []),
            ["Sign-in", user.auth === "both" ? "Password + Google" : user.auth === "google" ? "Google" : "Password"]].map(([k, v]) => (
            <div key={k} className="flex justify-between gap-4 border-b border-line pb-2 last:border-0">
              <dt className="text-ink-3">{k}</dt><dd className="font-semibold text-right">{v}</dd>
            </div>
          ))}
        </dl>
      </Tile>
      <Tile className="lg:col-span-7" eyebrow="Password recovery" title="Recovery code" icon={KeyRound}>
        {code ? (
          <RecoveryCodeCard code={code} email={user.email} doneLabel="Done" onDone={() => { setCode(null); refresh(); toast("New recovery code saved", "success"); }} />
        ) : (
          <form onSubmit={regenerate} className="space-y-3">
            <p className="text-sm text-ink-2">
              {user.has_recovery_code
                ? "You have a recovery code. If you lost it, create a new one: the old code stops working."
                : "You don't have a recovery code yet. Create one so you can reset your password without an admin."}
            </p>
            {needsPassword && (
              <input className="field" type="password" placeholder="Current password" value={password} autoComplete="current-password"
                     onChange={(e) => setPassword(e.target.value)} required aria-label="Current password" />
            )}
            {error && <ErrorNote>{error}</ErrorNote>}
            <button className="btn-primary" disabled={busy || (needsPassword && !password)}>
              {busy && <Loader2 className="w-4 h-4 animate-spin" />}{user.has_recovery_code ? "Create a new recovery code" : "Create my recovery code"}
            </button>
          </form>
        )}
      </Tile>
    </div>
  );
}
