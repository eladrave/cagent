# Session Persistence Architecture Fix

## Current Problem

The agent execution is tied to the HTTP request context. When a browser tab closes or the connection drops, the context is cancelled and the agent stops processing immediately.

### Code Flow:
1. `runAgent()` creates context from HTTP request: `context.WithCancel(c.Request().Context())`
2. Runtime uses this context for execution: `rt.RunStream(streamCtx, sess)`
3. When browser closes → request context cancelled → agent stops

## Why This Is Wrong

Sessions should be **background jobs** that:
- Continue running regardless of client connection
- Can be reconnected to at any time
- Stream events to clients when connected
- Continue processing when disconnected

## Proposed Solution

### Option 1: Background Context (Quick Fix)
Replace the request-bound context with a background context:

```go
// Instead of:
streamCtx, cancel := context.WithCancel(c.Request().Context())

// Use:
streamCtx, cancel := context.WithCancel(context.Background())
```

But also need to:
- Store events in memory/database for later retrieval
- Handle reconnection to existing streams
- Clean up completed sessions

### Option 2: Job Queue Architecture (Proper Fix)
1. **Submit jobs to queue**: When `/sessions/:id/agent/:agent` is called, submit a job
2. **Background workers**: Process jobs independently of HTTP connections
3. **Event storage**: Store events in database/cache
4. **SSE for real-time**: Stream stored events + new events when client connects
5. **Reconnection support**: Client can reconnect and get all missed events

### Option 3: Hybrid Approach (Recommended)
Combine both for immediate improvement:

```go
func (s *Server) runAgent(c echo.Context) error {
    // ... existing code ...
    
    // Check if session already has a running context
    s.cancelsMu.Lock()
    existingCancel, hasExisting := s.runtimeCancels[sess.ID]
    s.cancelsMu.Unlock()
    
    if hasExisting {
        // Session already running, just stream existing + new events
        return s.streamExistingSession(c, sess.ID)
    }
    
    // Start new background execution
    backgroundCtx, cancel := context.WithTimeout(context.Background(), 60*time.Minute)
    s.cancelsMu.Lock()
    s.runtimeCancels[sess.ID] = cancel
    s.cancelsMu.Unlock()
    
    // Start background processing
    go func() {
        defer func() {
            s.cancelsMu.Lock()
            delete(s.runtimeCancels, sess.ID)
            s.cancelsMu.Unlock()
        }()
        
        eventStore := make([]Event, 0, 1000)
        streamChan := rt.RunStream(backgroundCtx, sess)
        
        for event := range streamChan {
            // Store event for later retrieval
            s.storeEvent(sess.ID, event)
            eventStore = append(eventStore, event)
        }
        
        // Mark session as completed
        sess.Status = "completed"
        s.sessionStore.UpdateSession(context.Background(), sess)
    }()
    
    // Stream events to current client
    return s.streamSessionEvents(c, sess.ID)
}
```

## Implementation Steps

### Phase 1: Quick Fix (Immediate)
1. Change context to background context
2. Add timeout based on Cloud Run limits (60 minutes)
3. Test with long-running sessions

### Phase 2: Event Persistence
1. Add event storage to database/Redis
2. Implement event replay on reconnection
3. Add session status tracking

### Phase 3: Full Job Queue
1. Implement job queue (Cloud Tasks/Pub/Sub)
2. Move processing to background workers
3. Full reconnection support

## Benefits

1. **Resilient Sessions**: Continue even if user closes tab
2. **Reconnectable**: User can check back later
3. **Better UX**: No lost work due to connection issues
4. **Scalable**: Can process many sessions in parallel

## Testing

1. Start a session
2. Close browser tab immediately
3. Wait 30 seconds
4. Reconnect to session
5. Verify processing continued and history is available