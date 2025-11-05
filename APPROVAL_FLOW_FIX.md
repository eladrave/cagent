# Tool Approval Flow Fix

## Current Problem

When an agent needs tool approval:
1. It sends a `ToolCallConfirmation` event
2. It blocks waiting for a resume signal
3. If the client is disconnected, they never see this event
4. When they reconnect, there's no indication that approval is needed
5. The agent is stuck waiting forever (or until timeout)

## Issues to Fix

### 1. Approval Request Not Persisted
- Approval requests are sent as events, not saved as messages
- When users reconnect, they don't see what's waiting for approval

### 2. No Way to Resume Disconnected Sessions
- The resume endpoint requires an active runtime
- If the runtime timed out or the instance restarted, there's no way to resume

### 3. Poor User Experience
- Users don't know their agent is waiting for approval
- No way to respond to approval requests after reconnection

## Proposed Solution

### Phase 1: Persist Approval Requests (Implemented)
Add approval requests as messages in the session so they're visible when reconnecting:

```go
approvalMsg := chat.Message{
    Role:      chat.MessageRoleAssistant,
    Content:   fmt.Sprintf("I need approval to use the '%s' tool. Please approve or reject this action.", tool.Name),
    CreatedAt: time.Now().Format(time.RFC3339),
    ToolCalls: []tools.ToolCall{toolCall}, // Store for later processing
}
sess.AddMessage(session.NewAgentMessage(a, &approvalMsg))
```

### Phase 2: Handle Approval Responses (TODO)

#### Option 1: Special Commands in Messages
Allow users to send approval as a regular message:
- "approve" or "yes" → Approve the pending tool
- "reject" or "no" → Reject the pending tool
- "approve all" → Approve all tools for this session

#### Option 2: Dedicated Approval Endpoint
Create `/api/sessions/:id/approve` endpoint that:
1. Checks for pending approval in last assistant message
2. If runtime exists, sends resume signal
3. If no runtime, creates new runtime and continues from approval point

#### Option 3: Auto-Resume on Reconnect
When starting a runtime for a session with pending approval:
1. Check if last assistant message has ToolCalls
2. Automatically continue from that point
3. Either auto-approve or wait for new approval

### Phase 3: Better Status Indication

Add session status field:
```go
type Session struct {
    // ... existing fields ...
    Status string `json:"status"` // "active", "waiting_approval", "completed", "error"
    PendingApproval *PendingApproval `json:"pending_approval,omitempty"`
}

type PendingApproval struct {
    ToolName string `json:"tool_name"`
    ToolCall tools.ToolCall `json:"tool_call"`
    RequestedAt time.Time `json:"requested_at"`
}
```

## Implementation Steps

### Step 1: Update Runtime (DONE)
✅ Add approval messages to session

### Step 2: Update Message Handler
- Check if message is an approval response
- If yes, handle specially instead of sending to agent

### Step 3: Update Session Resumption
- When creating runtime for existing session
- Check for pending approvals
- Automatically continue from that state

### Step 4: Update Web UI
- Show approval requests clearly
- Add approve/reject buttons
- Show session status

## Testing

1. Start a session that requires tool approval
2. Disconnect immediately
3. Reconnect and see approval request message
4. Send "approve" message
5. Verify agent continues and executes tool

## Benefits

1. **Persistent State**: Approval requests survive disconnections
2. **Clear Communication**: Users see what's waiting for approval
3. **Flexible Response**: Can approve via message or dedicated endpoint
4. **Better UX**: Clear indication of session status