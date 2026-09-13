# Working in this repository

Read [CLAUDE.md](CLAUDE.md) for the project architecture, commands, and conventions.

## Temporary servers and test resources

The user's preference is to clean up development and Docker test resources when
work is finished. Keep a preview running only when the user explicitly requests it.
Opening a PR or sharing a preview link does not change this default.

- Before starting services, note which processes, ports, and Compose projects
  already exist. Track every service you start: command, working directory,
  process/tool-session ID, ports, and Compose file/project name.
- Before the final response, stop the temporary dev servers and test stacks you
  started. Prefer Ctrl-C through the original tool session; otherwise verify a
  process's command and working directory before sending SIGTERM. Avoid broad
  `pkill`, `killall`, Docker prune, or stopping Docker itself.
- The isolated stack in `docker-compose.test.yml` is disposable. Tear it down with:

  ```bash
  docker compose -f docker-compose.test.yml -p fridge-reliability down --volumes --remove-orphans
  ```

- The normal `docker-compose.yml` stack uses real app configuration and data.
  Preserve its `data/` directory and existing database/photos. Leave pre-existing
  services and unrelated containers alone unless the user asks to stop them.
- Clean up synthetic cloud users, photos, and scratch schemas created by tests;
  use `finally` blocks and report any cleanup failure. Never delete existing user
  data as part of test cleanup.
- Close browser tabs you created for temporary previews. Verify that the stopped
  services no longer appear in Docker and that their ports are no longer listening.
  Common ports here are dev `5173`/`8000`, normal Compose `8080`/`8000`, and isolated
  tests `18080`/`18000`/`55432`. Check the actual launch record for alternate ports.
- If the user asks to keep a service running, state its URL and exact stop command
  in the final response. Otherwise, briefly confirm cleanup is complete.
