# Git Details

Useful commands for working with Git and switching between office and personal GitHub accounts.

## Check Current Config

```bash
git config --global user.name
git config --global user.email
gh auth status
```

## Switch GitHub Account

Use this when you want to switch between your office and personal GitHub account.

```bash
gh auth switch --hostname github.com --user shahwar-coder
```

## Common Git Commands

```bash
git status
git add .
git commit -m "your message"
git push
git pull
git branch
git checkout <branch-name>
git switch <branch-name>
```

## Set Identity For A Repo

If a repository should use a specific identity:

```bash
git config user.name "Your Name"
git config user.email "you@example.com"
```

For this personal project, use the local repository config:

```bash
git config --local user.name "shahwar-coder"
git config --local user.email "naqvishahwar120@gmail.com"
```

Verify the local repo identity with:

```bash
git config --local user.name
git config --local user.email
```

## Set Global Identity

```bash
git config --global user.name "Your Name"
git config --global user.email "you@example.com"
```

## Notes

- `gh auth switch` changes the active GitHub CLI account for GitHub operations.
- `git config` controls the identity attached to commits.
- If a repo uses a different identity than your global config, the repo-local config takes precedence.

## Switch Back To Office Account

When you need to move this repo back to your office account, follow these steps:

1. Switch the active GitHub CLI account.

```bash
gh auth switch --hostname github.com --user Shahwar-Estrel
```

2. Update the repo-local Git identity to the office details.

```bash
git config --local user.name "Shahwar-Estrel"
git config --local user.email "shahwar.naqvi@estrel"
```

3. Verify the active account and local identity.

```bash
gh auth status
git config --local user.name
git config --local user.email
```

4. If you want to return to the personal account later, rerun the same commands with your personal GitHub username, name, and email.

## Current Office Values

```bash
gh auth switch --hostname github.com --user Shahwar-Estrel
git config --local user.name "Shahwar-Estrel"
git config --local user.email "shahwar.naqvi@estrel"
```
