import { useEffect, useRef, useState } from "react";
import { Bot, Send, StopCircle, User, Wrench, ChevronDown, ChevronUp, Loader2 } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { streamChat, type ChatMessage, type SSEEvent } from "../lib/chat";
import { cn } from "../lib/utils";

// ── Types ─────────────────────────────────────────────────────────────────────

interface ToolCall {
  name: string;
  args: Record<string, unknown>;
  result?: string;
}

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  toolCalls?: ToolCall[];
  isStreaming?: boolean;
}

// ── Suggested prompts ─────────────────────────────────────────────────────────

const SUGGESTIONS = [
  "What is Danone's current B Corp score and how does it compare to peers?",
  "What are employees saying about Danone's working conditions on Glassdoor?",
  "Where are the biggest gaps between Danone's CSR claims and public perception?",
  "Summarize the latest ESG risks for Danone from this week's news.",
  "What is Danone's stance on water rights and what are critics saying?",
  "Give me a marketing brief on Danone's social impact for an investor deck.",
];

// ── Tool call display ─────────────────────────────────────────────────────────

function ToolCallBadge({ tc }: { tc: ToolCall }) {
  const [expanded, setExpanded] = useState(false);
  const queryStr =
    tc.args.query ??
    tc.args.url ??
    (Array.isArray(tc.args.urls) ? tc.args.urls[0] : null) ??
    tc.args.sql ??
    "";

  return (
    <div className="mt-2 rounded-lg border border-slate-700 bg-slate-800/60 text-xs overflow-hidden">
      <button
        onClick={() => setExpanded((p) => !p)}
        className="flex w-full items-center gap-2 px-3 py-2 text-left text-slate-400 hover:bg-slate-700/40 transition-colors"
      >
        <Wrench size={12} className="text-amber-400 flex-shrink-0" />
        <span className="font-mono text-amber-300">{tc.name}</span>
        {queryStr && (
          <span className="truncate text-slate-500 flex-1">
            — {String(queryStr).slice(0, 80)}
          </span>
        )}
        <span className="ml-auto text-slate-600">
          {expanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
        </span>
      </button>

      {expanded && (
        <div className="border-t border-slate-700 px-3 py-2 space-y-1">
          <div className="text-slate-400">
            <span className="text-slate-500">Args: </span>
            <code className="text-green-400 break-all">
              {JSON.stringify(tc.args, null, 2)}
            </code>
          </div>
          {tc.result && (
            <div className="text-slate-400 mt-1">
              <span className="text-slate-500">Result preview: </span>
              <span className="text-slate-300">{tc.result}</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Typing indicator (bouncing dots) ─────────────────────────────────────────

function TypingIndicator() {
  return (
    <div className="flex items-center gap-1 px-4 py-3 bg-slate-800 border border-slate-700 rounded-2xl rounded-tl-sm w-fit">
      <span className="w-2 h-2 rounded-full bg-blue-400 animate-bounce [animation-delay:0ms]" />
      <span className="w-2 h-2 rounded-full bg-blue-400 animate-bounce [animation-delay:150ms]" />
      <span className="w-2 h-2 rounded-full bg-blue-400 animate-bounce [animation-delay:300ms]" />
    </div>
  );
}

// ── Message bubble ────────────────────────────────────────────────────────────

function MessageBubble({ msg }: { msg: Message }) {
  const isUser = msg.role === "user";
  const isThinking = !isUser && msg.isStreaming && !msg.content && (!msg.toolCalls || msg.toolCalls.length === 0);

  return (
    <div className={cn("flex gap-3", isUser ? "flex-row-reverse" : "flex-row")}>
      {/* Avatar */}
      <div
        className={cn(
          "flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center text-white",
          isUser ? "bg-blue-600" : "bg-slate-700",
        )}
      >
        {isUser ? (
          <User size={15} />
        ) : msg.isStreaming ? (
          <Loader2 size={15} className="animate-spin text-blue-400" />
        ) : (
          <Bot size={15} />
        )}
      </div>

      {/* Content */}
      <div className={cn("flex-1 max-w-[85%]", isUser ? "items-end" : "items-start")}>
        {/* Tool calls (assistant only) */}
        {!isUser && msg.toolCalls && msg.toolCalls.length > 0 && (
          <div className="mb-2 space-y-1">
            {msg.toolCalls.map((tc, i) => (
              <ToolCallBadge key={i} tc={tc} />
            ))}
          </div>
        )}

        {/* Typing indicator: shown while waiting for first token */}
        {isThinking && <TypingIndicator />}

        {/* Text bubble */}
        {msg.content && (
          <div
            className={cn(
              "rounded-2xl px-4 py-3 text-sm leading-relaxed",
              isUser
                ? "bg-blue-600 text-white rounded-tr-sm whitespace-pre-wrap"
                : "bg-slate-800 text-slate-100 rounded-tl-sm border border-slate-700",
            )}
          >
            {isUser ? (
              msg.content
            ) : (
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  h1: ({ children }) => <h1 className="text-base font-bold text-white mt-3 mb-1 first:mt-0">{children}</h1>,
                  h2: ({ children }) => <h2 className="text-sm font-bold text-white mt-3 mb-1 first:mt-0">{children}</h2>,
                  h3: ({ children }) => <h3 className="text-sm font-semibold text-slate-200 mt-2 mb-1 first:mt-0">{children}</h3>,
                  p:  ({ children }) => <p className="mb-2 last:mb-0 text-slate-100 leading-relaxed">{children}</p>,
                  ul: ({ children }) => <ul className="mb-2 space-y-0.5 pl-4 list-disc marker:text-blue-400">{children}</ul>,
                  ol: ({ children }) => <ol className="mb-2 space-y-0.5 pl-4 list-decimal marker:text-blue-400">{children}</ol>,
                  li: ({ children }) => <li className="text-slate-200 leading-relaxed">{children}</li>,
                  strong: ({ children }) => <strong className="font-semibold text-white">{children}</strong>,
                  em: ({ children }) => <em className="italic text-slate-300">{children}</em>,
                  code: ({ children, className }) => {
                    const isBlock = className?.includes("language-");
                    return isBlock ? (
                      <code className="block bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 my-2 text-xs font-mono text-green-300 overflow-x-auto whitespace-pre">
                        {children}
                      </code>
                    ) : (
                      <code className="bg-slate-900 border border-slate-700 rounded px-1.5 py-0.5 text-xs font-mono text-amber-300">
                        {children}
                      </code>
                    );
                  },
                  pre: ({ children }) => <>{children}</>,
                  blockquote: ({ children }) => (
                    <blockquote className="border-l-2 border-blue-500 pl-3 my-2 text-slate-400 italic">
                      {children}
                    </blockquote>
                  ),
                  hr: () => <hr className="border-slate-700 my-3" />,
                  a: ({ href, children }) => (
                    <a href={href} target="_blank" rel="noopener noreferrer"
                      className="text-blue-400 hover:text-blue-300 underline underline-offset-2 transition-colors">
                      {children}
                    </a>
                  ),
                  table: ({ children }) => (
                    <div className="overflow-x-auto my-2">
                      <table className="text-xs border-collapse w-full">{children}</table>
                    </div>
                  ),
                  th: ({ children }) => <th className="border border-slate-600 bg-slate-700 px-2 py-1 text-left font-semibold text-slate-200">{children}</th>,
                  td: ({ children }) => <td className="border border-slate-700 px-2 py-1 text-slate-300">{children}</td>,
                }}
              >
                {msg.content}
              </ReactMarkdown>
            )}
            {msg.isStreaming && (
              <span className="inline-block w-1.5 h-4 bg-blue-400 animate-pulse ml-0.5 align-text-bottom" />
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Empty state ───────────────────────────────────────────────────────────────

function EmptyState({ onSuggest }: { onSuggest: (q: string) => void }) {
  return (
    <div className="flex flex-col items-center justify-center h-full gap-6 py-12 px-4">
      <div className="w-16 h-16 rounded-2xl bg-blue-600/20 flex items-center justify-center">
        <Bot size={32} className="text-blue-400" />
      </div>
      <div className="text-center">
        <h2 className="text-xl font-semibold text-white mb-1">ESG Intelligence Assistant</h2>
        <p className="text-sm text-slate-400 max-w-md">
          Ask anything about Danone's social impact — I'll search the web, analyze NGO reports,
          and query our processed ESG data in real time.
        </p>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 max-w-2xl w-full">
        {SUGGESTIONS.map((s) => (
          <button
            key={s}
            onClick={() => onSuggest(s)}
            className="text-left px-4 py-3 rounded-xl border border-slate-700 bg-slate-800/50 hover:bg-slate-800 hover:border-blue-600/50 text-sm text-slate-300 transition-colors"
          >
            {s}
          </button>
        ))}
      </div>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function Chat() {
  const [messages, setMessages]       = useState<Message[]>([]);
  const [input, setInput]             = useState("");
  const [isStreaming, setIsStreaming]  = useState(false);
  const abortRef                      = useRef<AbortController | null>(null);
  const bottomRef                     = useRef<HTMLDivElement | null>(null);
  const textareaRef                   = useRef<HTMLTextAreaElement | null>(null);

  // Auto-scroll to bottom
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Auto-resize textarea
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 180)}px`;
  }, [input]);

  const buildHistory = (): ChatMessage[] =>
    messages
      .filter((m) => !m.isStreaming)
      .map((m) => ({ role: m.role, content: m.content }));

  const sendMessage = async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || isStreaming) return;

    const userMsg: Message = {
      id:   `u-${Date.now()}`,
      role: "user",
      content: trimmed,
    };

    const assistantMsg: Message = {
      id:         `a-${Date.now()}`,
      role:       "assistant",
      content:    "",
      toolCalls:  [],
      isStreaming: true,
    };

    setMessages((prev) => [...prev, userMsg, assistantMsg]);
    setInput("");
    setIsStreaming(true);

    const controller = new AbortController();
    abortRef.current = controller;

    const assistantId = assistantMsg.id;

    try {
      await streamChat(
        trimmed,
        buildHistory(),
        (event: SSEEvent) => {
          setMessages((prev) =>
            prev.map((m) => {
              if (m.id !== assistantId) return m;
              switch (event.type) {
                case "token":
                  return { ...m, content: m.content + event.content };
                case "tool_call":
                  return {
                    ...m,
                    toolCalls: [
                      ...(m.toolCalls ?? []),
                      { name: event.name, args: event.args },
                    ],
                  };
                case "tool_result": {
                  const tcs = [...(m.toolCalls ?? [])];
                  const last = tcs.findLastIndex((tc: ToolCall) => tc.name === event.name && !tc.result);
                  if (last !== -1) tcs[last] = { ...tcs[last], result: event.content };
                  return { ...m, toolCalls: tcs };
                }
                case "done":
                  return { ...m, isStreaming: false };
                case "error":
                  return { ...m, content: m.content || `Error: ${event.content}`, isStreaming: false };
                default:
                  return m;
              }
            }),
          );
        },
        controller.signal,
      );
    } catch (err: unknown) {
      if ((err as Error)?.name !== "AbortError") {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId
              ? { ...m, content: "An unexpected error occurred. Please try again.", isStreaming: false }
              : m,
          ),
        );
      }
    } finally {
      setIsStreaming(false);
      abortRef.current = null;
    }
  };

  const handleStop = () => {
    abortRef.current?.abort();
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage(input);
    }
  };

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center gap-3 px-6 py-4 border-b border-slate-800 flex-shrink-0">
        <div className="w-8 h-8 rounded-lg bg-blue-600/20 flex items-center justify-center">
          <Bot size={18} className="text-blue-400" />
        </div>
        <div>
          <h1 className="font-semibold text-white text-sm">ESG Intelligence Assistant</h1>
          <p className="text-xs text-slate-400">Powered by GPT 5.4 · You.com · Brightdata</p>
        </div>
        {isStreaming && (
          <span className="ml-auto text-xs text-blue-400 flex items-center gap-2">
            <Loader2 size={13} className="animate-spin" />
            Thinking…
          </span>
        )}
      </div>

      {/* Message list */}
      <div className="flex-1 overflow-y-auto px-4 py-6 space-y-6">
        {messages.length === 0 ? (
          <EmptyState onSuggest={(q) => sendMessage(q)} />
        ) : (
          messages.map((msg) => <MessageBubble key={msg.id} msg={msg} />)
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input area */}
      <div className="flex-shrink-0 border-t border-slate-800 px-4 py-4">
        <div className="flex gap-2 items-end max-w-4xl mx-auto">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            rows={1}
            placeholder="Ask about Danone's ESG performance, CSR claims, employee sentiment..."
            disabled={isStreaming}
            className={cn(
              "flex-1 resize-none rounded-xl border border-slate-700 bg-slate-800 px-4 py-3",
              "text-sm text-slate-100 placeholder:text-slate-500",
              "focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500/50",
              "disabled:opacity-50 disabled:cursor-not-allowed",
              "overflow-y-auto",
            )}
          />
          {isStreaming ? (
            <button
              onClick={handleStop}
              className="flex-shrink-0 w-10 h-10 rounded-xl bg-red-600 hover:bg-red-500 flex items-center justify-center text-white transition-colors"
              title="Stop generation"
            >
              <StopCircle size={18} />
            </button>
          ) : (
            <button
              onClick={() => sendMessage(input)}
              disabled={!input.trim()}
              className={cn(
                "flex-shrink-0 w-10 h-10 rounded-xl flex items-center justify-center text-white transition-colors",
                input.trim()
                  ? "bg-blue-600 hover:bg-blue-500"
                  : "bg-slate-700 cursor-not-allowed opacity-50",
              )}
              title="Send (Enter)"
            >
              <Send size={16} />
            </button>
          )}
        </div>
        <p className="text-center text-xs text-slate-600 mt-2">
          Shift+Enter for new line · Enter to send
        </p>
      </div>
    </div>
  );
}
