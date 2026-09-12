import "./Navbar.css";

import {
  FaBell,
  FaSearch,
  FaCircle,
  FaShieldAlt,
  FaSignOutAlt,
  FaVideo,
  FaServer,
} from "react-icons/fa";

import { getUser, clearSession } from "../../services/auth";

import {
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import { useNavigate } from "react-router-dom";

import api from "../../services/api";

import {
  getProfilePhoto,
  setProfilePhoto,
} from "../../services/profile";


function Navbar({ time }) {

  const navigate = useNavigate();

  const user = getUser();


  // =========================================================
  // STATE
  // =========================================================

  const [query, setQuery] = useState("");

  const [cameras, setCameras] = useState([]);

  const [nvrs, setNvrs] = useState([]);

  const [open, setOpen] = useState(false);

  const [selectedIndex, setSelectedIndex] = useState(-1);

  const [profilePhoto, setProfilePhotoState] =
    useState(getProfilePhoto);


  const profileInputRef = useRef(null);

  const searchRef = useRef(null);


  // =========================================================
  // PROFILE PHOTO REFRESH
  // =========================================================

  useEffect(() => {

    const refreshPhoto = () => {
      setProfilePhotoState(getProfilePhoto());
    };


    window.addEventListener(
      "visionguard-profile-photo-changed",
      refreshPhoto
    );


    return () => {

      window.removeEventListener(
        "visionguard-profile-photo-changed",
        refreshPhoto
      );

    };

  }, []);


  // =========================================================
  // PROFILE PHOTO CHANGE
  // =========================================================

  const handlePhotoChange = async (event) => {

    const file = event.target.files?.[0];

    if (!file) {
      return;
    }


    try {

      const photo = await setProfilePhoto(file);

      setProfilePhotoState(photo);

    } catch (error) {

      window.alert(
        error.message ||
        "Unable to change profile photo."
      );

    } finally {

      event.target.value = "";

    }

  };


  // =========================================================
  // LOGOUT
  // =========================================================

  const logout = () => {

    clearSession();

    navigate(
      "/login",
      {
        replace: true,
      }
    );

  };


  // =========================================================
  // LOAD CAMERA + NVR DATA
  // =========================================================

  const loadSearchData = async () => {

    try {

      const [
        cameraRes,
        nvrRes,
      ] = await Promise.all([
        api.get("/cameras"),
        api.get("/nvr/status"),
      ]);


      const cameraData =
        Array.isArray(cameraRes?.data)
          ? cameraRes.data
          : [];


      const nvrData =
        Array.isArray(nvrRes?.data)
          ? nvrRes.data
          : [];


      setCameras(cameraData);

      setNvrs(nvrData);

    } catch (error) {

      console.error(
        "Global search data loading failed:",
        error
      );

    }

  };


  useEffect(() => {

    let active = true;


    const firstLoad = async () => {

      if (!active) {
        return;
      }

      await loadSearchData();

    };


    firstLoad();


    // Refresh data every 30 seconds.
    // Office network connect hone ke baad
    // new camera/NVR data automatically aa jayega.

    const refreshTimer = setInterval(
      () => {

        if (active) {
          loadSearchData();
        }

      },
      30000
    );


    return () => {

      active = false;

      clearInterval(refreshTimer);

    };

  }, []);


  // =========================================================
  // CLOSE SEARCH WHEN CLICKING OUTSIDE
  // =========================================================

  useEffect(() => {

    const onOutside = (event) => {

      if (
        searchRef.current &&
        !searchRef.current.contains(
          event.target
        )
      ) {

        setOpen(false);

        setSelectedIndex(-1);

      }

    };


    document.addEventListener(
      "mousedown",
      onOutside
    );


    return () => {

      document.removeEventListener(
        "mousedown",
        onOutside
      );

    };

  }, []);


  // =========================================================
  // NORMALIZE SEARCH
  // =========================================================

  const normalize = (value) => {

    return String(value || "")
      .toLocaleLowerCase()
      .replace(/[\W_]+/gu, "");

  };


  // =========================================================
  // SEARCH RESULTS
  // =========================================================

  const results = useMemo(() => {

    const qRaw =
      query
        .trim()
        .toLocaleLowerCase();


    const q =
      normalize(qRaw);


    if (!q) {
      return [];
    }


    const resultList = [];


    // =======================================================
    // CAMERA SEARCH
    // =======================================================

    cameras.forEach((camera) => {

      const name =
        camera?.name ||
        camera?.camera_name ||
        camera?.cameraName ||
        `CH-${camera?.id || ""}`;


      const ip =
        camera?.ip ||
        camera?.ip_address ||
        camera?.ipAddress ||
        "";


      const nvr =
        camera?.nvr ||
        camera?.nvr_name ||
        camera?.nvrName ||
        "";


      const id =
        camera?.id ||
        camera?.channel ||
        camera?.channel_id ||
        "";


      const fields = [
        name,
        ip,
        nvr,
        id,
      ].map(normalize);


      const rawText = `
        ${name}
        ${ip}
        ${nvr}
        ${id}
      `.toLocaleLowerCase();


      const matched =
        fields.some(
          (field) =>
            field.includes(q)
        ) ||
        rawText.includes(qRaw);


      if (!matched) {
        return;
      }


      resultList.push({

        type: "camera",

        title: String(name),

        meta:
          `${nvr || "NVR"}` +
          ` · CH-${id || "--"}` +
          ` · ${ip || "No IP"}`,

        path:
          `/cameras?search=${encodeURIComponent(
            name || ip || id
          )}`,

        icon: <FaVideo />,

      });

    });


    // =======================================================
    // NVR SEARCH
    // =======================================================

    nvrs.forEach((nvr) => {

      const name =
        nvr?.name ||
        nvr?.nvr_name ||
        nvr?.nvrName ||
        nvr?.title ||
        "NVR";


      const ip =
        nvr?.ip ||
        nvr?.ip_address ||
        nvr?.ipAddress ||
        "";


      const port =
        nvr?.port ||
        nvr?.http_port ||
        "";


      const fields = [
        name,
        ip,
        port,
      ].map(normalize);


      const rawText = `
        ${name}
        ${ip}
        ${port}
      `.toLocaleLowerCase();


      const matched =
        fields.some(
          (field) =>
            field.includes(q)
        ) ||
        rawText.includes(qRaw);


      if (!matched) {
        return;
      }


      resultList.push({

        type: "nvr",

        title: String(name),

        meta:
          `${ip || "No IP"}` +
          `${port ? ` · Port ${port}` : ""}`,

        path:
          `/nvr?search=${encodeURIComponent(
            name || ip
          )}`,

        icon: <FaServer />,

      });

    });


    // =======================================================
    // REMOVE DUPLICATES
    // =======================================================

    const uniqueResults =
      resultList.filter(
        (item, index, array) =>
          index ===
          array.findIndex(
            (other) =>
              other.type === item.type &&
              other.title === item.title &&
              other.meta === item.meta
          )
      );


    // =======================================================
    // PRIORITY
    //
    // Camera first
    // NVR second
    // =======================================================

    uniqueResults.sort(
      (a, b) => {

        const priority = {
          camera: 1,
          nvr: 2,
        };


        return (
          (priority[a.type] || 9) -
          (priority[b.type] || 9)
        );

      }
    );


    return uniqueResults.slice(
      0,
      10
    );

  }, [
    query,
    cameras,
    nvrs,
  ]);


  // =========================================================
  // OPEN RESULT
  // =========================================================

  const openResult = (item) => {

    if (!item) {
      return;
    }


    navigate(item.path);


    setOpen(false);

    setSelectedIndex(-1);

  };


  // =========================================================
  // SEARCH
  // =========================================================

  const goSearch = () => {

    const q =
      query.trim();


    if (!q) {
      return;
    }


    // Selected suggestion
    if (
      selectedIndex >= 0 &&
      results[selectedIndex]
    ) {

      openResult(
        results[selectedIndex]
      );

      return;

    }


    // First suggestion
    if (results.length > 0) {

      openResult(
        results[0]
      );

      return;

    }


    // Existing fallback
    navigate(
      `/cameras?search=${encodeURIComponent(q)}`
    );


    setOpen(false);

  };


  // =========================================================
  // KEYBOARD SEARCH
  // =========================================================

  const handleSearchKeyDown = (event) => {

    // DOWN
    if (
      event.key === "ArrowDown"
    ) {

      event.preventDefault();


      if (!results.length) {
        return;
      }


      setSelectedIndex(
        (previous) =>
          previous >= results.length - 1
            ? 0
            : previous + 1
      );


      return;

    }


    // UP
    if (
      event.key === "ArrowUp"
    ) {

      event.preventDefault();


      if (!results.length) {
        return;
      }


      setSelectedIndex(
        (previous) =>
          previous <= 0
            ? results.length - 1
            : previous - 1
      );


      return;

    }


    // ENTER
    if (
      event.key === "Enter"
    ) {

      event.preventDefault();

      goSearch();

      return;

    }


    // ESC
    if (
      event.key === "Escape"
    ) {

      setOpen(false);

      setSelectedIndex(-1);

    }

  };


  // =========================================================
  // CLEAR SEARCH
  // =========================================================

  const clearSearch = () => {

    setQuery("");

    setOpen(false);

    setSelectedIndex(-1);

  };


  // =========================================================
  // RENDER
  // =========================================================

  return (

    <header className="navbar">


      {/* =====================================================
          LEFT / LOGO
          ===================================================== */}

      <div className="navbar-left">

        <div className="logo-box">

          <FaShieldAlt
            className="logo-icon"
          />

        </div>


        <div className="logo-text">

          <h2>

            VisionGuard{" "}

            <span className="brand-ai">
              AI
            </span>

          </h2>


          <p>
            TATA 1MG Security Operations Center
          </p>

        </div>

      </div>


      {/* =====================================================
          GLOBAL SEARCH
          ===================================================== */}

      <div
        className="navbar-center"
        ref={searchRef}
      >

        <div className="search-box">

          <FaSearch
            className="search-icon"
          />


          <input
            value={query}

            onChange={(event) => {

              setQuery(
                event.target.value
              );

              setOpen(true);

              setSelectedIndex(-1);

            }}

            onFocus={() => {

              if (
                query.trim()
              ) {

                setOpen(true);

              }

            }}

            onKeyDown={
              handleSearchKeyDown
            }

            type="search"

            placeholder="Search Camera, NVR, IP Address..."

            aria-label="Global search"

            autoComplete="off"
          />


          {query && (

            <button
              type="button"
              className="search-clear"
              onClick={clearSearch}
              aria-label="Clear search"
            >

              ×

            </button>

          )}

        </div>


        {/* =================================================
            SUGGESTION DROPDOWN
            ================================================= */}

        {open &&
          query.trim() && (

            <div className="global-search-results">


              {results.length > 0 ? (

                results.map(
                  (item, index) => (

                    <button
                      key={
                        `${item.type}-${item.title}-${index}`
                      }

                      type="button"

                      className={
                        `global-search-item ${
                          selectedIndex === index
                            ? "selected"
                            : ""
                        }`
                      }

                      onMouseDown={(event) => {

                        event.preventDefault();

                        openResult(item);

                      }}

                      onMouseEnter={() => {

                        setSelectedIndex(
                          index
                        );

                      }}
                    >


                      <span
                        className={
                          `global-result-icon ${item.type}`
                        }
                      >

                        {item.icon}

                      </span>


                      <span className="global-result-content">

                        <strong>
                          {item.title}
                        </strong>


                        <small>
                          {item.meta}
                        </small>

                      </span>


                      <span className="global-result-type">

                        {item.type === "camera"
                          ? "CAMERA"
                          : "NVR"}

                      </span>


                    </button>

                  )

                )

              ) : (

                <div className="global-search-empty">

                  <FaSearch />

                  <span>
                    No camera, NVR or IP match found.
                  </span>

                </div>

              )}

            </div>

          )}

      </div>


      {/* =====================================================
          RIGHT
          ===================================================== */}

      <div className="navbar-right">


        {/* LIVE MONITORING */}

        <div className="live-status">

          <FaCircle
            className="live-dot"
          />

          <span>
            Live Monitoring
          </span>

        </div>


        {/* CLOCK */}

        <div className="clock">

          🕒 {time}

        </div>


        {/* NOTIFICATIONS */}

        <button
          className="notification"
          aria-label="Notifications"
          type="button"
        >

          <FaBell />

          <span className="badge">
            3
          </span>

        </button>


        {/* ACCOUNT */}

        <div className="account-card">


          <div className="account-main">


            <button
              type="button"
              className="account-photo-button"
              onClick={() =>
                profileInputRef.current?.click()
              }
              title="Change profile photo"
              aria-label="Change profile photo"
            >

              <img
                src={profilePhoto}
                alt="Profile"
                className="account-photo"
              />

            </button>


            <input
              ref={profileInputRef}
              type="file"
              accept="image/*"
              onChange={handlePhotoChange}
              hidden
            />


            <div className="profile-info">

              <strong>
                {user?.username || "User"}
              </strong>


              <small>
                {user?.role || "Viewer"}
              </small>

            </div>


          </div>


          <button
            className="account-logout"
            onClick={logout}
            type="button"
          >

            <FaSignOutAlt />

            <span>
              Logout
            </span>

          </button>


        </div>


      </div>


    </header>

  );

}


export default Navbar;