import "../styles/layout.css";
import { useEffect, useState } from "react";

import Sidebar from "../components/Sidebar/Sidebar";
import Navbar from "../components/Navbar/Navbar";

function Layout({ children }) {
  const [time, setTime] = useState("");

  useEffect(() => {
    const timer = setInterval(() => {
      setTime(
        new Date().toLocaleTimeString("en-IN", {
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
        })
      );
    }, 1000);

    return () => clearInterval(timer);
  }, []);

  return (
    <div className="layout">

      <Sidebar />

      <div className="content">

        <Navbar time={time} />

        <main className="main">
          {children}
        </main>

      </div>

    </div>
  );
}

export default Layout;