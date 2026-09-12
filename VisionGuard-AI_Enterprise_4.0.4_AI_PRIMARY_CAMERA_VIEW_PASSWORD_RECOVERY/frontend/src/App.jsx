import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import Layout from "./layout/Layout";
import Dashboard from "./pages/Dashboard";
import Cameras from "./pages/Cameras";
import NVR from "./pages/NVR";
import NVRControlCenter from "./pages/NVRControlCenter";
import Alerts from "./pages/Alerts";
import Analytics from "./pages/Analytics";
import Settings from "./pages/Settings";
import Storage from "./pages/Storage";
import Users from "./pages/Users";
import FloorMap from "./pages/FloorMap";
import CameraMovements from "./pages/CameraMovements";
import LiveView from "./pages/LiveView";
import Reports from "./pages/Reports";
import HealthCenter from "./pages/HealthCenter";
import Diagnostics from "./pages/Diagnostics";
import HistoricalRecordingFinder from "./pages/HistoricalRecordingFinder";
import AuditLog from "./pages/AuditLog";
import WhatsAppAlerts from "./pages/WhatsAppAlerts";
import Login from "./pages/Login";
import ResetPassword from "./pages/ResetPassword";
import { getUser, isAuthenticated } from "./services/auth";

function RequireAuth({ children }) {
  return isAuthenticated() ? children : <Navigate to="/login" replace />;
}

function RequireAdmin({ children }) {
  const user = getUser();
  const role = String(user?.role || "").toLowerCase();
  return role === "administrator" || role === "admin" ? children : <Navigate to="/" replace />;
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/reset-password" element={<ResetPassword />} />
        <Route path="*" element={
          <RequireAuth>
            <Layout>
              <Routes>
                <Route path="/" element={<Dashboard />} />
                <Route path="/cameras" element={<Cameras />} />
                <Route path="/nvr" element={<NVR />} />
                <Route path="/nvr-control" element={<RequireAdmin><NVRControlCenter /></RequireAdmin>} />
                <Route path="/alerts" element={<Alerts />} />
                <Route path="/analytics" element={<Analytics />} />
                <Route path="/settings" element={<RequireAdmin><Settings /></RequireAdmin>} />
                <Route path="/storage" element={<Storage />} />
                <Route path="/users" element={<RequireAdmin><Users /></RequireAdmin>} />
                <Route path="/floor-map" element={<FloorMap />} />
                <Route path="/camera-movements" element={<CameraMovements />} />
                <Route path="/live" element={<LiveView />} />
                <Route path="/reports" element={<Reports />} />
                <Route path="/health-center" element={<HealthCenter />} />
                <Route path="/diagnostics" element={<Diagnostics />} />
                <Route path="/historical-recordings" element={<HistoricalRecordingFinder />} />
                <Route path="/audit" element={<RequireAdmin><AuditLog /></RequireAdmin>} />
                <Route path="/whatsapp-alerts" element={<RequireAdmin><WhatsAppAlerts /></RequireAdmin>} />
                <Route path="*" element={<Navigate to="/" replace />} />
              </Routes>
            </Layout>
          </RequireAuth>
        } />
      </Routes>
    </BrowserRouter>
  );
}
