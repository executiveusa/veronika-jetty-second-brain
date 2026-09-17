# Database credential rotation

Status: staged. Do not run without Jeremy present.

The old credential was removed from the current tracked configuration, but it remains in Git history and must be treated as exposed. This runbook rotates the live credential without placing the replacement in Git, chat, logs, screenshots, or command history.

## Before the sit-down

- [ ] Confirm the production database host and the exact database role used by Jetty.
- [ ] Confirm the managed secret store used by the VPS/deployment platform.
- [ ] Take a database backup and perform a restore check in an isolated environment.
- [ ] Record the currently deployed Jetty commit and container/image ID.
- [ ] Confirm a maintenance window and rollback owner.

## Rotation, with Jeremy present

1. Create a new random password in the database control plane. Do not paste it into chat or a shell command.
2. Save the new DSN as `VERONIKA_PG_DSN` in the managed deployment secret store.
3. Restart only the Jetty service so it reads the new secret.
4. Verify `/api/health`, database connection logs, one tenant-safe write, and one readback.
5. Revoke the old password only after the new path passes.
6. Re-run the health and readback checks after revocation.
7. Record only the rotation time, operator, affected role, and verification result. Never record the secret.

## Rollback

If the new credential does not work before the old password is revoked, restore the previous secret-store version and restart Jetty. If failure occurs after revocation, create another new credential and update the managed secret. Never restore the exposed password.

## Git history

The exposed value exists in prior commits. Rewriting public history is disruptive and does not make a leaked credential safe. Rotate first. Decide separately whether to rewrite history, with a coordinated clone/branch plan.
