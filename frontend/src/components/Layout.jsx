import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../auth/AuthProvider";
import Particles from "./Particles";

const link = ({ isActive }) =>
  `font-display text-xs tracking-[0.2em] uppercase pb-1 border-b-2 transition-colors ${
    isActive ? "text-gold-hi border-hex" : "text-ink border-transparent hover:text-gold"
  }`;

function HexLogo() {
  return (
    <svg width="34" height="34" viewBox="0 0 34 34" aria-hidden>
      <polygon points="17,2 31,10 31,24 17,32 3,24 3,10" fill="none" stroke="#C8AA6E" strokeWidth="1.6" />
      <polygon points="17,9 25,13.5 25,20.5 17,25 9,20.5 9,13.5" fill="rgba(10,200,185,.15)" stroke="#0AC8B9" strokeWidth="1.2" />
    </svg>
  );
}

export default function Layout() {
  const { user, signOut } = useAuth();
  return (
    <div className="relative min-h-screen">
      <Particles />
      <header className="relative z-10 border-b border-gold/30 bg-abyss/80 backdrop-blur">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center gap-6 px-4 py-3">
          <div className="flex items-center gap-3">
            <HexLogo />
            <span className="font-display text-lg font-bold tracking-[0.25em] text-gold">HEXTECH ARCHIVE</span>
          </div>
          <nav className="flex gap-6">
            <NavLink to="/" end className={link}>Archivista</NavLink>
            <NavLink to="/documents" className={link}>Documentos</NavLink>
            <NavLink to="/history" className={link}>Historial</NavLink>
          </nav>
          <div className="ml-auto flex items-center gap-3">
            <span className="hidden text-sm text-ink sm:inline">{user?.email}</span>
            <button className="btn-ghost" onClick={signOut}>Salir</button>
          </div>
        </div>
      </header>
      <main className="relative z-10 mx-auto max-w-5xl px-4 py-6">
        <Outlet />
      </main>
    </div>
  );
}
