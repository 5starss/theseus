import * as vscode from 'vscode';

export interface InlineContext {
    editor: vscode.TextEditor;
    selection: vscode.Selection;
}

export interface InlineInputProvider {
    /**
     * 프롬프트를 사용자에게 요청하여 입력받습니다.
     * @param context 현재 에디터 및 선택 영역 정보
     * @returns 사용자가 입력한 문자열, 취소 시 undefined
     */
    prompt(context: InlineContext): Promise<string | undefined>;
}

export class NativeInputProvider implements InlineInputProvider {
    public async prompt(context: InlineContext): Promise<string | undefined> {
        return await vscode.window.showInputBox({
            prompt: 'Theseus Edit: 수정할 내용을 입력하세요 (Ctrl+I)',
            placeHolder: 'e.g. Extract this logic into a helper function',
            ignoreFocusOut: false
        });
    }
}
