import * as vscode from 'vscode';
import { TheseusSessionManager } from '../session/SessionManager';
import { InlineInputProvider, NativeInputProvider } from './InlineInputProvider';
import { InlineDiffManager } from './InlineDiffManager';

export class InlineEditController implements vscode.Disposable {
    private inputProvider: InlineInputProvider;
    private diffManager: InlineDiffManager;
    private disposables: vscode.Disposable[] = [];
    private isEditing = false;
    private currentRunSessionId: string | undefined;

    constructor(private readonly sessionManager: TheseusSessionManager) {
        this.inputProvider = new NativeInputProvider();
        this.diffManager = new InlineDiffManager();

        this.disposables.push(
            vscode.commands.registerCommand('theseus.inlineEdit', this.handleInlineEdit.bind(this))
        );

        this.disposables.push(
            this.sessionManager.onEvent(this.handleRunnerEvent.bind(this))
        );
    }

    private async handleInlineEdit() {
        const editor = vscode.window.activeTextEditor;
        if (!editor || this.isEditing) return;

        const selection = editor.selection;
        
        const userInput = await this.inputProvider.prompt({ editor, selection });
        if (!userInput) return; // User cancelled

        const selectedText = editor.document.getText(selection);
        
        const prompt = `[INLINE EDIT REQUEST]
File: ${editor.document.fileName}
Lines: ${selection.start.line + 1}-${selection.end.line + 1}
Selected Code:
\`\`\`
${selectedText}
\`\`\`

Instruction: ${userInput}

CRITICAL: Output ONLY the raw replacement code. Do not wrap it in markdown blocks (e.g. \`\`\`python). Do not explain anything. Just output the code.`;

        this.isEditing = true;
        this.diffManager.clear();
        this.diffManager.startStream(editor, selection);
        
        // Use ASK mode so it doesn't use tools and streams text directly
        this.sessionManager.send(prompt, 'ASK');
    }

    private handleRunnerEvent(event: any) {
        if (!this.isEditing) return;

        if (event.type === 'AssistantTextDelta' && event.text) {
            // Stream the text into the editor
            this.diffManager.appendDelta(event.text);
        } else if (event.type === 'AssistantTurnComplete' || event.type === 'StatusEvent') {
            if (event.type === 'StatusEvent' && event.state !== 'ready') return;
            // Finished
            this.diffManager.finishStream();
            this.isEditing = false;
        } else if (event.type === 'RunnerStopped' || event.type === 'RunnerError') {
            this.diffManager.finishStream();
            this.isEditing = false;
        }
    }

    dispose() {
        this.diffManager.clear();
        this.disposables.forEach(d => d.dispose());
    }
}
