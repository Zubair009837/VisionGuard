import { NavLink } from "react-router-dom";

import {
  FaHome,
  FaVideo,
  FaServer,
  FaBell,
  FaCog,
  FaChartBar,
  FaMapMarkedAlt,
  FaDatabase,
  FaUsers,
  FaFileAlt,
  FaBroadcastTower,
  FaCheckCircle,
  FaHeartbeat,
  FaStethoscope,
  FaHistory,
  FaSearch,
  FaWhatsapp,
} from "react-icons/fa";

import "./Sidebar.css";
import { getUser } from "../../services/auth";

function Sidebar() {
  const user = getUser();

  const isAdmin = ["administrator", "admin"].includes(
    String(user?.role || "").toLowerCase()
  );

  const menuItems = [
    {
      name: "Dashboard",
      icon: <FaHome />,
      path: "/",
    },

    {
      name: "Live View",
      icon: <FaBroadcastTower />,
      path: "/live",
    },

    {
      name: "Historical Recording Finder",
      icon: <FaSearch />,
      path: "/historical-recordings",
    },

    {
      name: "Cameras",
      icon: <FaVideo />,
      path: "/cameras",
    },

    {
      name: "NVR",
      icon: <FaServer />,
      path: "/nvr",
    },

    {
      name: "NVR Control Center",
      icon: <FaServer />,
      path: "/nvr-control",
      adminOnly: true,
    },

    {
      name: "Health Center",
      icon: <FaHeartbeat />,
      path: "/health-center",
    },

    {
      name: "Alerts",
      icon: <FaBell />,
      path: "/alerts",
    },

    {
      name: "WhatsApp Alerts",
      icon: <FaWhatsapp />,
      path: "/whatsapp-alerts",
      adminOnly: true,
    },

    {
      name: "Camera Movement",
      icon: <FaBroadcastTower />,
      path: "/camera-movements",
    },

    {
      name: "Analytics",
      icon: <FaChartBar />,
      path: "/analytics",
    },

    {
      name: "Floor Map",
      icon: <FaMapMarkedAlt />,
      path: "/floor-map",
    },

    {
      name: "Storage",
      icon: <FaDatabase />,
      path: "/storage",
    },

    {
      name: "Users",
      icon: <FaUsers />,
      path: "/users",
      adminOnly: true,
    },

    {
      name: "Reports",
      icon: <FaFileAlt />,
      path: "/reports",
    },

    {
      name: "Diagnostics",
      icon: <FaStethoscope />,
      path: "/diagnostics",
    },

    {
      name: "Audit Log",
      icon: <FaHistory />,
      path: "/audit",
      adminOnly: true,
    },

    {
      name: "Settings",
      icon: <FaCog />,
      path: "/settings",
      adminOnly: true,
    },
  ];

  return (
    <aside className="sidebar">

      {/* Navigation */}

      <nav className="menu">

        {menuItems
          .filter((item) => !item.adminOnly || isAdmin)
          .map((item) => (
            <NavLink
              key={item.name}
              to={item.path}
              className={({ isActive }) =>
                isActive
                  ? "menu-item active"
                  : "menu-item"
              }
            >

              <span className="icon">
                {item.icon}
              </span>

              <span className="menu-text">
                {item.name}
              </span>

            </NavLink>
          ))}

      </nav>


      {/* Developer Information */}

      <div className="developer-box">

        <div className="developer-title">
          <strong>Owned By</strong>
        </div>

        <div className="developer-name">
          👑 Zubair Khan
        </div>

        <div className="developer-desc">
          Enterprise Security Platform Creator
        </div>

      </div>


      {/* Footer */}

      <div className="sidebar-footer">

        <div className="status-dot"></div>

        <span>
          Enterprise Monitoring Active
        </span>

      </div>

    </aside>
  );
}

export default Sidebar;