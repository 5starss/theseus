import * as path from 'path';
import * as vscode from 'vscode';
import type { RunnerEvent } from '../shared/protocol';

export type ChangedFileMetadata = {
  path?: string;
  relative_path?: string;
  existed_before?: boolean;
  old_content?: string;
};

export class TheseusDiffContentProvider implements vscode.TextDocumentContentProvider {
  private readonly documents = new Map<string, string>();
  private readonly emitter = new vscode.EventEmitter<vscode.Uri>();
  readonly onDidChange = this.emitter.event;

  createUri(label: string, content: string): vscode.Uri {
    const id = `${Date.now()}-${Math.random().toString(36).slice(2)}`;
    this.documents.set(id, content);
    return vscode.Uri.from({
      scheme: 'theseus-diff',
      path: `/${path.basename(label) || 'previous'}`,
      query: id,
    });
  }

  provideTextDocumentContent(uri: vscode.Uri): string {
    return this.documents.get(uri.query) ?? '';
  }
}

export function getChangedFile(event: RunnerEvent): ChangedFileMetadata | undefined {
  const metadata = event.metadata;
  const changed = metadata?.changed_file;
  if (!changed || typeof changed !== 'object') return undefined;
  return changed as ChangedFileMetadata;
}
