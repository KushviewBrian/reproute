import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { ClerkProvider, useAuth } from "@clerk/clerk-react";
import "maplibre-gl/dist/maplibre-gl.css";

import { App } from "./pages/App";
import "./styles/app.css";

const clerkPubKey = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY || "";
const pocMode = import.meta.env.VITE_POC_MODE === "true";

function ClerkApp() {
  const { getToken } = useAuth();
  const [token, setToken] = React.useState<string | undefined>(undefined);

  React.useEffect(() => {
    getToken().then((t) => setToken(t ?? undefined));
  }, [getToken]);

  return (
    <BrowserRouter>
      <App token={token} authRequired />
    </BrowserRouter>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    {pocMode ? (
      <BrowserRouter>
        <App token={undefined} authRequired={false} />
      </BrowserRouter>
    ) : (
      <ClerkProvider publishableKey={clerkPubKey}>
        <ClerkApp />
      </ClerkProvider>
    )}
  </React.StrictMode>
);
