---
title: Git and GitHub questions
summary: Commits, branches, merge versus rebase, resolving conflicts, undoing changes and pull requests.
kind: qa
takeaways:
- Know the everyday Git commands and the three areas of Git
- Explain merge versus rebase and reset versus revert
- Describe a normal pull request workflow
---
### Q [Easy] What is Git and how is it different from GitHub?
**Git** is a distributed version control system that tracks changes to files. **GitHub** is a website that hosts Git repositories and adds collaboration features (pull requests, issues, actions).

### Q [Easy] What are the three areas in Git?
The **working directory** (your files), the **staging area** (changes marked for the next commit with `git add`) and the **repository** (committed history).

### Q [Easy] Explain the basic workflow commands.
```bash
git clone <url>          # copy a repository
git status               # see what changed
git add file.py          # stage a change
git commit -m "Fix login bug"
git push origin main     # send commits to the remote
git pull                 # fetch and merge from the remote
```

### Q [Easy] `git fetch` vs `git pull`?
`fetch` downloads new commits from the remote but does **not** change your working files. `pull` is a `fetch` followed by a merge (or rebase) into your current branch.

### Q [Medium] What is a branch and why use branches?
A separate line of development. Branches let you work on a feature or a fix without disturbing the main code. Create with `git switch -c feature/login` and merge back when ready.

### Q [Medium] `git merge` vs `git rebase`?
**Merge** joins two branches and keeps the full history with a merge commit. **Rebase** moves your commits on top of another branch, creating a **linear** history but rewriting the commits. Do not rebase commits that others already use (shared branches).

### Q [Medium] What is a merge conflict and how do you resolve it?
When two branches change the same lines, Git cannot decide automatically. Open the marked files (`<<<<<<<`, `=======`, `>>>>>>>`), choose or combine the correct code, remove the markers, then `git add` the files and finish the merge or commit.

### Q [Medium] `git reset` vs `git revert`?
`reset` moves the branch pointer back and can erase commits (dangerous on shared history). `revert` creates a **new commit that undoes** an earlier one, so history stays safe. Use `revert` for commits already pushed.

### Q [Medium] How do you undo changes?
- Discard uncommitted changes in a file: `git restore file.py`.
- Unstage: `git restore --staged file.py`.
- Change the last commit message: `git commit --amend` (before pushing).
- Undo a pushed commit safely: `git revert <commit>`.

### Q [Medium] What is `git stash`?
Temporarily saves your uncommitted changes so you can switch branches with a clean working directory; restore with `git stash pop`.

### Q [Medium] What is `.gitignore`?
A file listing patterns of files Git should not track, such as `node_modules/`, `.env`, `__pycache__/` and build output. Never commit secrets.

### Q [Medium] What is a pull request?
A request to merge your branch into another (usually `main`) on GitHub. Teammates review the code, comment, and CI checks run before it is merged.

### Q [Medium] Fork vs clone?
**Clone** copies a repository to your computer. **Fork** copies someone else's repository to your own GitHub account so you can change it and propose changes with a pull request.

### Q [Hard] What is `git cherry-pick`?
Applies a single commit from one branch to another without merging the whole branch.

### Q [Hard] What happens if you commit a password by mistake?
Treat it as **leaked**: change the password or revoke the key immediately. Removing it from later commits is not enough because it stays in history; tools such as `git filter-repo` can remove it from history, but the secret must still be rotated.
