// When a screen throws, show what threw. React unmounts the whole tree on an uncaught render
// error, and the engineer is left looking at a white page with nothing to report but "it went
// blank" - which is the hardest kind of fault to fix, because the one fact that would identify it
// is the one thing that was thrown away.

import { Component, type ErrorInfo, type ReactNode } from "react";

interface State {
  error: Error | null;
  where: string | null;
}

export class Crash extends Component<{ children: ReactNode }, State> {
  state: State = { error: null, where: null };

  static getDerivedStateFromError(error: Error): Partial<State> {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    this.setState({ where: info.componentStack ?? null });
    console.error("fastcae: a screen threw", error, info.componentStack);
  }

  render() {
    const { error, where } = this.state;
    if (!error) return this.props.children;
    return (
      <div className="crash">
        <h2>That screen stopped.</h2>
        <p>
          The rest of the session is intact - nothing being computed is affected. Reload to carry
          on, and send this along if it keeps happening.
        </p>
        <pre>
          {error.name}: {error.message}
          {where ? `\n${where}` : ""}
        </pre>
        <button type="button" onClick={() => this.setState({ error: null, where: null })}>
          Try again
        </button>
      </div>
    );
  }
}
