import React from "react";
import { reportClientError } from "../utils/clientLogger";

export default class AppErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { failed: false };
  }

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidCatch(error, info) {
    reportClientError("react_render_failed", error, {
      component_stack: info.componentStack,
    });
  }

  render() {
    if (this.state.failed) {
      return (
        <main className="app-fatal-error" role="alert">
          <h1>Something went wrong</h1>
          <p>The interview application could not render this screen.</p>
          <button type="button" onClick={() => globalThis.location?.reload()}>
            Reload application
          </button>
        </main>
      );
    }
    return this.props.children;
  }
}
