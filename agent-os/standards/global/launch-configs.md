# Launch Configs

Every executable Python script has an entry in `.vscode/launch.json`, so it can be stepped through
in a real debugger (`F5`) as easily as it runs from the shell.

"Executable" means a `scripts/*.py` file with an `if __name__ == "__main__":` block, plus the
package entry point (`weather_story_bot`, the dev CLI). Add the entry in the same change that adds
the script.

- Name it `<Script Name>: <What It Does>`, as in `Migrate Table Keys: Dry Run`
- Use `"type": "debugpy"`, `"request": "launch"`, `"cwd": "${workspaceFolder}"` and
  `"console": "integratedTerminal"`. Use `"program"` for a script and `"module"` for the package
- **The entry is safe to launch without thinking.** It never passes `--apply`, and a tool that
  would otherwise touch AWS sets `"env": {"AWS_PROFILE": "readonly"}` so it can't write even if
  someone adds `--apply` later (`global/principles`). A tool that can only run with the MFA profile
  gets no entry; document why in its docstring
- Give it `args` that work on a clean checkout. When a script reads something `make` produces
  (`build/package`), say so in a `//` comment on the entry
- Write output to a scratch path (`build/debug.zip`), never to a file another step consumes
  (`build/lambda.zip`). A debug session must not change what `make plan` hashes or `make deploy` applies
- A script with subcommands gets one entry per subcommand worth stepping through
