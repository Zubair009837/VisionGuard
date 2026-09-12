function Loader({ text = "Loading..." }) {
  return (
    <div
      className="d-flex flex-column justify-content-center align-items-center"
      style={{ height: "70vh" }}
    >
      <div
        className="spinner-border text-primary mb-3"
        style={{ width: "3rem", height: "3rem" }}
        role="status"
      >
        <span className="visually-hidden">Loading...</span>
      </div>

      <h4 className="text-white">{text}</h4>

      <small className="text-secondary mt-2">
        Please wait...
      </small>
    </div>
  );
}

export default Loader;