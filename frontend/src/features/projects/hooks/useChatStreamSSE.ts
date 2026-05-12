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
  output?: string;
  status?: string;
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
    prompt: string
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
      body: JSON.stringify({ mode, prompt }),
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
              store.setProgressInfo({
                step: data.message || 'Agent working',
                message: data.message || '',
                percent: 0,
              });
              break;

            case 'tool_result':
              store.setProgressInfo({
                step: data.tool_name ? `Tool: ${data.tool_name}` : 'Tool result',
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
