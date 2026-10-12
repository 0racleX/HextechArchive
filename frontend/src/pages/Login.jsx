import { useState } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "../auth/AuthProvider";
import Frame from "../components/Frame";
import Particles from "../components/Particles";

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export default function Login() {
  const { session, signIn, signUp } = useAuth();
  const [mode, setMode] = useState("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");
  const [busy, setBusy] = useState(false);

  if (session) return <Navigate to="/" replace />;

  async function submit(e) {
    e.preventDefault();
    setError(""); setInfo("");
    if (!EMAIL_RE.test(email)) return setError("Ingresa un correo válido.");
    if (password.length < 8) return setError("La contraseña debe tener al menos 8 caracteres.");
    setBusy(true);
    const { data, error: err } = mode === "login" ? await signIn(email, password) : await signUp(email, password);
    setBusy(false);
    if (err) return setError(err.message);
    if (mode === "register" && !data.session) setInfo("Cuenta creada. Revisa tu correo para confirmarla.");
  }

  return (
    <div className="relative grid min-h-screen place-items-center px-4">
      <Particles />
      <Frame className="relative z-10 w-full max-w-md p-8">
        <h1 className="mb-1 text-center text-3xl font-black">HEXTECH ARCHIVE</h1>
        <p className="mb-6 text-center italic text-ink">El Archivista de Runeterra aguarda tu pregunta.</p>
        <form onSubmit={submit} className="space-y-4" noValidate>
          <label className="block">
            <span className="font-display text-xs tracking-widest text-gold">CORREO</span>
            <input className="field mt-1" type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} />
          </label>
          <label className="block">
            <span className="font-display text-xs tracking-widest text-gold">CONTRASEÑA</span>
            <input className="field mt-1" type="password" autoComplete={mode === "login" ? "current-password" : "new-password"} value={password} onChange={(e) => setPassword(e.target.value)} />
          </label>
          {error && <p role="alert" className="text-ember">{error}</p>}
          {info && <p role="status" className="text-hex">{info}</p>}
          <button className="btn-gold w-full" disabled={busy}>{busy ? "Procesando…" : mode === "login" ? "Entrar" : "Crear cuenta"}</button>
        </form>
        <button className="mt-5 block w-full text-center text-sm text-ink hover:text-gold" onClick={() => { setMode(mode === "login" ? "register" : "login"); setError(""); setInfo(""); }}>
          {mode === "login" ? "¿Sin cuenta? Regístrate" : "¿Ya tienes cuenta? Inicia sesión"}
        </button>
      </Frame>
    </div>
  );
}
