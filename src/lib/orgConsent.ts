/**
 * Joining an organization is the learner's consent (DPDP Act 2023) to its
 * admins seeing their progress. Every join and first sign-in shows this text.
 */
export function orgSharingNotice(orgName: string): string {
  return `${orgName}'s admins can see your job readiness, levels, activity in every agent and your chats. `
    + "Leave the organization at any time to stop sharing.";
}

/** Before an organization is known (typing a join code). */
export const JOIN_NOTICE = "By joining, the organization's admins can see your job readiness, levels, activity in every "
  + "agent and your chats. Leave the organization at any time to stop sharing.";
