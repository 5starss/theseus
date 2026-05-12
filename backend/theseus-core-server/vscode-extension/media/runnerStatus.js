(function () {
  'use strict';

  function normalizeLifecycle(event) {
    return event.lifecycle || event.state || (event.running ? 'ready' : event.processRunning ? 'starting' : 'stopped');
  }

  function runnerDiagnosticText(event, fallbackDiagnostic) {
    const diagnostic = event?.lastDiagnostic || fallbackDiagnostic;
    if (!diagnostic?.message) return '';
    const details = [
      `Last runner diagnostic: ${diagnostic.code || 'unknown'}`,
      diagnostic.message,
    ];
    if (event?.pythonExec) details.push(`python: ${event.pythonExec}`);
    if (event?.cwd || event?.workspaceCwd) details.push(`cwd: ${event.cwd || event.workspaceCwd}`);
    if (event?.coreRoot) details.push(`core: ${event.coreRoot}`);
    if (event?.exitReason) details.push(`exit: ${event.exitReason}`);
    return details.join('\n');
  }

  window.TheseusRunnerStatus = {
    normalizeLifecycle,
    runnerDiagnosticText,
  };
}());
