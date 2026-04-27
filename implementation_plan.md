# Multi-User System Implementation Plan (M3 Integration Specialist)

We will proceed with completing the M3 Integration phase across four key areas: Calendar, Workspace, Notion, and Cleanup Logic. Since this involves structural changes across multiple files, handling it in logical phases will make it much smoother.

Below is the proposed breakdown.

## Proposed Phased Implementation

### Phase 1: Workspace Generation (Per-User Directories)
**Goal:** Scaffold dedicated local folders for each team member in the project workspace, reducing merge conflicts and delineating assignments.
- **MODIFY** `workspace_tool.py`:
  - Update `prepare_project_workspace` to accept a `team_members` list (e.g. `[{"name": "Alice", "role": "Backend"}]`).
  - Instead of just `src/` and `docs/`, the system will generate a sub-folder for *each* team member.
  - Inside each member's sub-folder, generate specific files tailored to their sub-role (e.g., a personalized README.md or `main.py`).

### Phase 2: Multi-User Calendar & Cleanup Logic
**Goal:** Distribute events into specific team members' Google calendars rather than a single unified "primary" calendar. Enhance robustness during plan refinement runs.
- **MODIFY** `calendar_tool.py`:
  - Modify `get_free_slots` to accept a `calendar_email` or investigate the busy statuses of multiple `team_emails` simultaneously.
  - Update `create_calendar_block` to accept a `calendar_email` to route the deep work block to the exact person responsible.
  - Implement **Cleanup Logic**: Track previously created event links/IDs (perhaps via project key and task name) so if a refinement run happens, we fetch existing events and Update/Delete them instead of piling on duplicate events.

### Phase 3: Multi-User Notion
**Goal:** Tag specific users on Notion Kanban cards and create segregated workspaces for them within the Notion Run page.
- **MODIFY** `notion_tool.py`:
  - Enhance `begin_notion_run_workspace` to establish not just the main Kanban board, but also "sub-folders" (Sub-pages or specific database views) for each teammate.
  - Update `create_kanban_card` to accept an `assignee_id` parameter. We will map team member emails or names to actual Notion User IDs so they are natively tagged on the tasks.

### Phase 4: API & Agents Orchestration Update
**Goal:** Tie all these tools together in the agent logic to ensure dynamically injected team configurations are passed down to the tools.
- **MODIFY** `agents.py` and `main.py`:
  - Make `TriggerRequest` in `main.py` flexible enough to accept team info from the user.
  - Update the `Tech Lead Agent` and `Scrum Master Agent` instructions to properly leverage the new parameters in `prepare_project_workspace`, `create_calendar_block`, and `create_kanban_card`.

## User Review Required

1. **Notion IDs & Emails:** To tag users in Notion and Google Calendar, the API will need corresponding user Notion IDs and Google account emails. Would you like to pass this array of users directly in the POST body to `/trigger-pipeline` (e.g., `[{"name": "Rahul", "email": "rahul@example.com", "notion_id": "xyz..."}]`)? 
2. **Duplicate Cleanup Storage:** For calendar deduplication, do you prefer storing active Event IDs in a lightweight local file (e.g., JSON state file during the run) or adding an `Event ID` field to the Notion Kanban board to act as the source of truth?

Please let me know if you approve of this phased approach, and I can immediately begin with **Phase 1** and **Phase 2**.
