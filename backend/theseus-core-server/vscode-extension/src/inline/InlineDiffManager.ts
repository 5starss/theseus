import * as vscode from 'vscode';

export class InlineDiffManager {
    private decorationType: vscode.TextEditorDecorationType;
    private currentEditor: vscode.TextEditor | undefined;
    private startPos: vscode.Position | undefined;
    private endPos: vscode.Position | undefined;
    
    constructor() {
        this.decorationType = vscode.window.createTextEditorDecorationType({
            backgroundColor: new vscode.ThemeColor('diffEditor.insertedTextBackground'),
            isWholeLine: false,
        });
    }

    public startStream(editor: vscode.TextEditor, selection: vscode.Selection) {
        this.currentEditor = editor;
        this.startPos = selection.start;
        // Delete the current selection if needed, or we just replace it.
        // Usually it's better to clear it first.
        this.endPos = selection.start;
        
        // Clear selection
        if (!selection.isEmpty) {
            editor.edit(editBuilder => {
                editBuilder.delete(selection);
            }).then(() => {
                this.endPos = this.startPos;
                this.updateDecorations();
            });
        }
    }

    public async appendDelta(text: string) {
        if (!this.currentEditor || !this.endPos) return;

        await this.currentEditor.edit(editBuilder => {
            editBuilder.insert(this.endPos!, text);
        }, { undoStopBefore: false, undoStopAfter: false });

        // Update end position
        const lines = text.split('\n');
        if (lines.length > 1) {
            this.endPos = new vscode.Position(
                this.endPos.line + lines.length - 1,
                lines[lines.length - 1].length
            );
        } else {
            this.endPos = this.endPos.translate(0, text.length);
        }

        this.updateDecorations();
    }

    public finishStream() {
        this.updateDecorations();
        // We can keep the decoration for a while, or clear it.
        // Let's keep it until the next action.
    }

    public clear() {
        if (this.currentEditor) {
            this.currentEditor.setDecorations(this.decorationType, []);
        }
        this.currentEditor = undefined;
        this.startPos = undefined;
        this.endPos = undefined;
    }

    private updateDecorations() {
        if (!this.currentEditor || !this.startPos || !this.endPos) return;
        const range = new vscode.Range(this.startPos, this.endPos);
        this.currentEditor.setDecorations(this.decorationType, [range]);
    }
}
