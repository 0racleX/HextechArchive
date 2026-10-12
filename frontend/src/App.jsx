import { Route, Routes } from "react-router-dom";
import ProtectedRoute from "./auth/ProtectedRoute";
import Layout from "./components/Layout";
import Login from "./pages/Login";
import Chat from "./pages/Chat";
import Documents from "./pages/Documents";
import History from "./pages/History";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route element={<ProtectedRoute><Layout /></ProtectedRoute>}>
        <Route path="/" element={<Chat />} />
        <Route path="/documents" element={<Documents />} />
        <Route path="/history" element={<History />} />
      </Route>
    </Routes>
  );
}
