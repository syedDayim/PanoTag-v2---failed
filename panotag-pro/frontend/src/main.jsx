import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { WsProvider } from "./WsContext.jsx";
import App from "./App.jsx";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <BrowserRouter>
      <WsProvider>
        <App />
      </WsProvider>
    </BrowserRouter>
  </React.StrictMode>
);
