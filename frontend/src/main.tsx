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
  const { getToken, isSignedIn, isLoaded } = useAuth();
  const [token, setToken] = React.useState<string | undefined>(undefined);

  // Refresh the token whenever sign-in state changes, and keep it fresh
  // by refreshing every 4 minutes (Clerk tokens expire after 60 min but
  // this keeps us well ahead of expiry in long sessions).
  React.useEffect(() => {
    if (!isLoaded || !isSignedIn) {
      setToken(undefined);
      return;
    }

    let cancelled = false;

    async function refresh() {
      const t = await getToken();
      if (!cancelled) setToken(t ?? undefined);
    }

    refresh();
    const interval = setInterval(refresh, 4 * 60 * 1000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [getToken, isLoaded, isSignedIn]);

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
