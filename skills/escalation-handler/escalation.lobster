# Escalation Workflow
# 4-level escalation chain with timeouts and approval gates

name: escalation
description: Multi-level escalation for unresolved fleet issues

inputs:
  - name: ESCALATION_ID
    description: Unique escalation identifier
    required: true
  - name: ASSET_ID
    description: Asset that triggered escalation
    required: true
  - name: TRIGGER
    description: What triggered the escalation
    required: true
  - name: MESSAGE
    description: Detailed message about the issue
    required: true

env:
  - SUPERVISOR_ID
  - SAFETY_ID
  - OWNER_ID
  - REDIS_URL

# Error handling: If telegram-send or redis-cli fails (network error, invalid token, etc.),
# commands retry up to 3 times with exponential backoff. If all retries fail, the step
# continues to on_timeout behavior. Errors are logged to memory/escalations/$ESCALATION_ID.log
error_handling:
  retry_count: 3
  retry_delay: 30s
  retry_backoff: exponential
  on_final_failure: continue_to_timeout

steps:
  # Level 1: Supervisor
  - name: notify_supervisor
    description: Notify supervisor via Telegram DM
    command: |
      telegram-send --to "$SUPERVISOR_ID" --message "$(cat <<EOF
      ⚠️ Escalation Alert - Level 1

      Asset: $ASSET_ID
      Issue: $TRIGGER
      Time: $(date -u +%Y-%m-%dT%H:%M:%SZ)
      Escalation ID: $ESCALATION_ID

      $MESSAGE

      Reply "ACK" to acknowledge, or "RESOLVED {notes}" to close.
      EOF
      )"
    timeout: 4h
    on_error: |
      echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] ERROR: Failed to notify supervisor" >> "memory/escalations/$ESCALATION_ID.log"
    on_response:
      - match: "^ACK$"
        action: acknowledge
        then: wait_for_resolution
      - match: "^RESOLVED"
        action: resolve
        then: complete
    on_timeout: notify_safety

  # Wait state after acknowledgment
  - name: wait_for_resolution
    description: Wait for resolution after acknowledgment
    command: |
      echo "Waiting for resolution from supervisor..."
    wait_for_message:
      - match: "^RESOLVED"
        action: resolve
        then: complete
    timeout: 24h
    on_timeout: notify_safety

  # Level 2: Safety Officer
  - name: notify_safety
    description: Notify safety officer via Telegram DM
    command: |
      telegram-send --to "$SAFETY_ID" --message "$(cat <<EOF
      🚨 Escalation Alert - Level 2

      Asset: $ASSET_ID
      Issue: $TRIGGER
      Time: $(date -u +%Y-%m-%dT%H:%M:%SZ)
      Escalation ID: $ESCALATION_ID

      Supervisor did not acknowledge within 4 hours.

      $MESSAGE

      Reply "ACK" to acknowledge.
      Reply "RESOLVED {notes}" to close.
      Reply "ESCALATE" to immediately proceed to Owner.
      EOF
      )"
    timeout: 2h
    on_error: |
      echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] ERROR: Failed to notify safety officer" >> "memory/escalations/$ESCALATION_ID.log"
    on_response:
      - match: "^ACK$"
        action: acknowledge
        then: wait_for_safety_resolution
      - match: "^RESOLVED"
        action: resolve
        then: complete
      - match: "^ESCALATE$"
        action: none
        then: notify_owner
    on_timeout: notify_owner

  # Wait state after safety acknowledgment
  - name: wait_for_safety_resolution
    description: Wait for resolution from safety officer
    command: |
      echo "Waiting for resolution from safety officer..."
    wait_for_message:
      - match: "^RESOLVED"
        action: resolve
        then: complete
      - match: "^ESCALATE$"
        action: none
        then: notify_owner
    timeout: 12h
    on_timeout: notify_owner

  # Level 3: Owner/Manager
  - name: notify_owner
    description: Notify owner/manager via Telegram DM
    command: |
      telegram-send --to "$OWNER_ID" --message "$(cat <<EOF
      🆘 Escalation Alert - Level 3

      Asset: $ASSET_ID
      Issue: $TRIGGER
      Time: $(date -u +%Y-%m-%dT%H:%M:%SZ)
      Escalation ID: $ESCALATION_ID

      Neither Supervisor nor Safety Officer have resolved this issue.

      $MESSAGE

      Reply "ACK" to acknowledge and take ownership.
      Reply "RESOLVED {notes}" to close.
      EOF
      )"
    timeout: 2h
    on_error: |
      echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] ERROR: Failed to notify owner" >> "memory/escalations/$ESCALATION_ID.log"
    on_response:
      - match: "^ACK$"
        action: acknowledge
        then: wait_for_owner_resolution
      - match: "^RESOLVED"
        action: resolve
        then: complete
    on_timeout: enter_critical

  # Wait state after owner acknowledgment
  - name: wait_for_owner_resolution
    description: Wait for resolution from owner
    command: |
      echo "Waiting for resolution from owner..."
    wait_for_message:
      - match: "^RESOLVED"
        action: resolve
        then: complete
    timeout: 24h
    on_timeout: enter_critical

  # Level 4: CRITICAL state
  - name: enter_critical
    description: Enter CRITICAL state with hourly broadcasts
    command: |
      # Update asset status to CRITICAL
      redis-cli -u "$REDIS_URL" PUBLISH "fleet:status" '{
        "asset_id": "'"$ASSET_ID"'",
        "status": "CRITICAL",
        "reason": "'"$TRIGGER"'",
        "escalation_id": "'"$ESCALATION_ID"'"
      }'

      echo "Asset $ASSET_ID entered CRITICAL state"
    then: critical_broadcast

  # Hourly CRITICAL broadcasts
  - name: critical_broadcast
    description: Broadcast CRITICAL status hourly
    command: |
      telegram-send --channel "$ESCALATION_CHANNEL" --message "$(cat <<EOF
      🆘 CRITICAL - Unresolved Escalation

      Asset: $ASSET_ID
      Issue: $TRIGGER
      Escalation ID: $ESCALATION_ID
      Duration: Escalation active since start

      This issue has not been acknowledged by Supervisor, Safety, or Owner.
      Immediate attention required.

      To resolve, any authorized party reply:
      RESOLVED $ESCALATION_ID {notes}
      EOF
      )"
    timeout: 1h
    on_response:
      - match: "^RESOLVED"
        action: resolve
        then: complete
    on_timeout: critical_broadcast  # Loop back for next broadcast

  # Completion
  - name: complete
    description: Escalation resolved
    command: |
      echo "Escalation $ESCALATION_ID resolved"

      # Update asset status if it was CRITICAL
      redis-cli -u "$REDIS_URL" PUBLISH "fleet:status" '{
        "asset_id": "'"$ASSET_ID"'",
        "status": "OPERATIONAL",
        "escalation_resolved": "'"$ESCALATION_ID"'"
      }'

# Action handlers
actions:
  acknowledge:
    description: Record acknowledgment
    command: |
      # Update escalation record
      echo "Acknowledged at $(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "memory/escalations/$ESCALATION_ID.log"

  resolve:
    description: Mark escalation as resolved
    command: |
      # Extract resolution notes from message
      NOTES=$(echo "$RESPONSE" | sed 's/^RESOLVED //')

      # Update escalation record
      cat >> "memory/escalations/$ESCALATION_ID.log" <<EOF

      RESOLVED at $(date -u +%Y-%m-%dT%H:%M:%SZ)
      By: $RESPONDER
      Notes: $NOTES
      EOF

      # Notify all parties
      telegram-send --to "$SUPERVISOR_ID" --message "✓ Escalation $ESCALATION_ID resolved: $NOTES"
      telegram-send --to "$SAFETY_ID" --message "✓ Escalation $ESCALATION_ID resolved: $NOTES"
      telegram-send --to "$OWNER_ID" --message "✓ Escalation $ESCALATION_ID resolved: $NOTES"
