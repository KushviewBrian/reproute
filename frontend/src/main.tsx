import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { ClerkProvider, useAuth } from "@clerk/clerk-react";
import "maplibre-gl/dist/maplibre-gl.css";

import { App } from "./pages/App";
import "./styles/app.css";

const clerkPubKey = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY || "";

function ClerkApp() {
  const { getToken, isSignedIn, isLoaded } = useAuth();
  const [token, setToken] = React.useState<string | undefined>(undefined);

  React.useEffect(() => {
    if (!isLoaded || !isSignedIn) {
      setToken(undefined);
      return;
    }

    let cancelled = false;

    async function refresh() {
      const t = await getToken({ template: "reproute" });
      if (!cancelled) setToken(t ?? undefined);
    }

    refresh();
    const interval = setInterval(refresh, 55 * 1000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [getToken, isLoaded, isSignedIn]);

  const refreshToken = React.useCallback(async () => {
    const t = await getToken({ template: "reproute" });
    if (t) setToken(t);
    return t ?? undefined;
  }, [getToken]);

  return (
    <BrowserRouter>
      <App token={token} refreshToken={refreshToken} />
    </BrowserRouter>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ClerkProvider publishableKey={clerkPubKey}>
      <ClerkApp />
    </ClerkProvider>
  </React.StrictMode>
);
