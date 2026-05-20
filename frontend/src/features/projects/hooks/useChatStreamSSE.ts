import { useCallback, useRef } from 'react';
import { fetchEventSource } from '@microsoft/fetch-event-source';
import { toast } from 'sonner';
import { useAuthStore } from '@/store/useAuthStore';
import { useChatSessionStore } from '../stores/useChatSessionStore';
import type { ToolPlanMode } from '../types/chat';

interface ChatStreamEvent {
  message?: string;
  content?: string;
  tool_name?: string;
  tool_use_id?: string;
  tool_input?: Record<string, unknown>;
  output?: string;
  status?: string;
  is_error?: boolean;
  total_tokens?: number;
  model_name?: string;
}

export function useChatStreamSSE() {
  const abortRef = useRef<AbortController | null>(null);

  const disconnectChatStream = useCallback(() => {
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
  }, []);

  const connectChatStream = useCallback((
    projectId: string,
    sessionId: string,
    mode: Extract<ToolPlanMode, 'ASK' | 'AGENT'>,
    prompt: string,
    remoteWorkspaceId?: number
  ) => {
    disconnectChatStream();

    const controller = new AbortController();
    abortRef.current = controller;
    useChatSessionStore.getState().setAbortController(controller);

    const baseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8080';
    const token = useAuthStore.getState().accessToken;

    void fetchEventSource(`${baseUrl}/api/v1/projects/${projectId}/sessions/${sessionId}/messages/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'text/event-stream',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({ mode, prompt, remoteWorkspaceId }),
      signal: controller.signal,
      openWhenHidden: true,

      async onopen(response) {
        if (!response.ok) {
          throw new Error(`Chat stream failed with status ${response.status}`);
        }
      },

      onmessage(ev) {
        if (!ev.data) return;

        try {
          const data = JSON.parse(ev.data) as ChatStreamEvent;
          const eventType = (ev.event || '').toLowerCase();
          const store = useChatSessionStore.getState();

          switch (eventType) {
            case 'connected':
              store.setProgressInfo({
                step: `${mode} connected`,
                message: data.message || '',
                percent: 0,
              });
              break;

            case 'chunk':
              if (data.content) {
                store.updateLastMessageContent(data.content);
              }
              break;

            case 'status':
              if (data.tool_name) {
                store.upsertToolExecutionNotice({
                  noticeType: 'TOOL_EXECUTION_STARTED',
                  toolName: data.tool_name,
                  toolUseId: data.tool_use_id || null,
                  toolInput: data.tool_input || {},
                  status: data.status || 'started',
                });
              }
              store.setProgressInfo({
                step: data.tool_name ? `Tool Running: ${data.tool_name}` : (data.message || 'Agent working'),
                message: data.message || '',
                percent: 0,
              });
              break;

            case 'tool_result':
              if (data.tool_name) {
                store.upsertToolExecutionNotice({
                  noticeType: data.is_error ? 'TOOL_EXECUTION_FAILED' : 'TOOL_EXECUTION_COMPLETED',
                  toolName: data.tool_name,
                  toolUseId: data.tool_use_id || null,
                  toolInput: data.tool_input || {},
                  output: data.output || '',
                  isError: data.is_error || false,
                  status: data.status || (data.is_error ? 'failed' : 'completed'),
                });
              }
              store.setProgressInfo({
                step: data.tool_name
                  ? `${data.is_error ? 'Tool Failed' : 'Tool Completed'}: ${data.tool_name}`
                  : (data.is_error ? 'Tool failed' : 'Tool completed'),
                message: data.output || '',
                percent: 0,
              });
              break;

            case 'completed':
              store.setIsGenerating(false);
              store.setProgressInfo(null);
              store.setAbortController(null);
              abortRef.current = null;
              break;

            case 'error': {
              const errorMessage = data.message || 'Chat stream failed.';
              store.setIsGenerating(false);
              store.setProgressInfo(null);
              store.setAbortController(null);
              store.addMessage({
                messageId: crypto.randomUUID(),
                senderType: 'SYSTEM_NOTICE',
                messageType: 'SYSTEM_NOTICE',
                contentType: 'TEXT',
                content: errorMessage,
                createdAt: new Date().toISOString(),
              });
              toast.error(errorMessage);
              disconnectChatStream();
              break;
            }

            default:
              console.warn('[ChatStream] Unknown event type:', eventType, data);
          }
        } catch (error) {
          console.warn('[ChatStream] Failed to handle event:', ev.data, error);
        }
      },

      onerror(error) {
        const store = useChatSessionStore.getState();
        store.setIsGenerating(false);
        store.setProgressInfo(null);
        store.setAbortController(null);
        abortRef.current = null;
        toast.error('Chat stream connection failed.');
        throw error;
      },
    }).catch((error) => {
      if (controller.signal.aborted) return;
      console.error('[ChatStream] Connection failed:', error);
    });
  }, [disconnectChatStream]);

  return { connectChatStream, disconnectChatStream };
}
