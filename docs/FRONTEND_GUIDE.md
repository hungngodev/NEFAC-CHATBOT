# NEFAC Frontend Documentation

## 1. Overview

The NEFAC Frontend is a modern **Next.js 15** application built with the **App Router**. It serves as the user interface for the LangGraph-based backend, providing a rich, streaming chat experience with support for multi-modal input, deep research toggles, and artifact visualization.

- **Framework**: Next.js 15.2+ (App Router).
- **Language**: TypeScript.
- **Styling**: Tailwind CSS 4 + Shadcn UI (Radix Primitives).
- **State Management**: `nuqs` (URL-based state), React Context (`StreamContext`).
- **Communication**: Server-Sent Events (SSE) via `@langchain/langgraph-sdk`.
- **Architecture**: Client-side heavy logic wrapped in server-side providers.

---

## 2. Routes & Layouts

The application uses the Next.js App Router structure (`src/app`).

### 2.1 File Structure

| Path              | Type          | Description                                                                                               |
| :---------------- | :------------ | :-------------------------------------------------------------------------------------------------------- |
| `/`               | Page          | The main chat interface (`page.tsx`). Renders the `Thread` component wrapped in context providers.        |
| `/api/[..._path]` | Route Handler | A proxy route that forwards requests to the LangGraph backend to handle CORS and authentication securely. |
| `layout.tsx`      | Root Layout   | Wraps the application in `NuqsAdapter` (for URL state) and applies global styles/fonts (`Inter`).         |

### 2.2 Layout Hierarchy

The application uses a provider-heavy root structure to manage global state:

```tsx
// src/app/page.tsx
<Suspense>
  <ThreadProvider>
    {" "}
    {/* Manages sidebar history state */}
    <StreamProvider>
      {" "}
      {/* Manages active chat stream & LangGraph connection */}
      <ArtifactProvider>
        {" "}
        {/* Manages the right-side artifact panel */}
        <Thread /> {/* Main UI Controller */}
      </ArtifactProvider>
    </StreamProvider>
  </ThreadProvider>
</Suspense>
```

---

## 3. Components

The core logic resides in `src/components/thread`.

### 3.1 Core Controller: `Thread` (`src/components/thread/index.tsx`)

This is the central component that orchestrates the UI.

- **Responsibilities**:
  - **Layout Management**: Toggles the left sidebar (`ThreadHistory`) and right sidebar (`ArtifactContent`).
  - **Input Handling**: Manages the chat input, file uploads (`useFileUpload`), and "Deep Research" toggle.
  - **Submission**: Calls `stream.submit()` to send messages to the backend.
  - **Rendering**: Maps over `messages` to render `HumanMessage` or `AssistantMessage`.
- **Key Hooks**:
  - `useStreamContext`: Accesses the LangGraph stream.
  - `useQueryState`: Syncs UI state (like `deepResearch` mode) with the URL.
  - `useStickToBottomContext`: Manages auto-scrolling behavior.

### 3.2 Sidebar Components

- **`ThreadHistory`** (`src/components/thread/history/index.tsx`):
  - Displays a list of past conversations.
  - Allows switching threads via `setThreadId`.
- **`ArtifactContent`** (`src/components/thread/artifact.tsx`):
  - Renders detailed content (e.g., generated reports, cited documents) in a dedicated side panel, keeping the chat stream clean.

### 3.3 Message Components

- **`HumanMessage`**: Renders user input.
### 3.3 Message Rendering & Tool Visualization
The chat interface uses specialized components to render complex AI behaviors.

*   **`AssistantMessage` (`src/components/thread/messages/ai.tsx`)**:
    *   **Tool Calls**: Renders `ToolCalls` component to show intermediate actions (e.g., "Searching for 'NEFAC'...") unless `hideToolCalls` is enabled.
    *   **Custom UI**: Supports `CustomComponent` for rendering backend-driven UI widgets (charts, maps) via `LoadExternalComponent`.
    *   **Citations**: Renders `DocumentList` at the bottom if `final_documents` are present in `additional_kwargs`.
    *   **Controls**: Includes `BranchSwitcher` (for navigating alternative generations) and `CommandBar` (for regeneration).

*   **`ReasoningBlock` (`src/components/thread/reasoning-block.tsx`)**:
    *   **Purpose**: Collapses verbose "Chain of Thought" or intermediate reasoning steps into a clean, expandable UI.
    *   **Structure**: Uses a `Collapsible` container with a `ScrollArea` to manage long traces without cluttering the main chat view.

## 4. Data Flow & API

### 4.1 Data Fetching (Streaming)

The app uses **Server-Sent Events (SSE)** for real-time communication.

- **Library**: `@langchain/langgraph-sdk`.
- **Flow**:
  1.  User submits a message in `Thread`.
  2.  `stream.submit()` is called with the message and configuration (e.g., `research_mode`).
  3.  Request hits `/api/runs/stream` (Next.js API Route).
  4.  Next.js proxies the request to the Python backend (`http://localhost:8123`).
  5.  Backend streams events back (tokens, tool updates, state changes).
  6.  `useStreamContext` updates the `messages` state in real-time.

### 4.2 State Management

- **URL State (`nuqs`)**:
  - `?threadId=...`: The active conversation ID.
  - `?deepResearch=true`: Toggles the "Deep Research" mode.
  - **Benefit**: Users can share URLs to specific states.
- **Optimistic UI**:
  - When a user sends a message, it is immediately added to the UI state via `optimisticValues` before the server responds.

### 4.3 API Proxy (`src/app/api/[..._path]/route.ts`)

- **Library**: `langgraph-nextjs-api-passthrough`.
- **Purpose**:
  - Avoids CORS issues between `localhost:3000` and `localhost:8123`.
  - Injects sensitive API keys (like `LANGSMITH_API_KEY`) server-side, keeping them out of the browser.

---

## 5. Setup & Dependencies

### 5.1 Environment Variables

Defined in `.env.local` (or `.env`).

- `NEXT_PUBLIC_API_URL`: The URL of the LangGraph backend (default: `http://localhost:8123`).
- `LANGSMITH_API_KEY`: (Optional) For tracing agent execution.

### 5.2 Key Dependencies (`package.json`)

- **Framework**: `next`, `react`, `react-dom`.
- **LangChain**: `@langchain/langgraph-sdk`, `langgraph-nextjs-api-passthrough`.
- **UI**: `tailwindcss`, `lucide-react`, `framer-motion`, `sonner` (Toasts).
- **State**: `nuqs` (URL state).
- **Markdown**: `react-markdown`, `rehype-katex` (Math support).

### 5.3 Development Setup

**Location**: `client/`
**Port**: `3000`

1.  **Install Dependencies**:
    ```bash
    cd client
    pnpm install
    ```

2.  **Configure Environment**:
    Create a local environment file pointing to your local backend:
    ```bash
    cp .env.example .env.local
    ```
    *Ensure `NEXT_PUBLIC_API_URL=http://localhost:8123` in `.env.local`.*

3.  **Start Frontend**:
    Run the Next.js development server:
    ```bash
    pnpm dev
    ```
    - **UI**: `http://localhost:3000`
