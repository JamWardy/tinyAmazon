# Working on tinyAmazon

- **Always `main`, in every repo.** The top level and every submodule
  work, commit and push on `main` only. Never make or switch to another
  branch.

- **Ask before deciding anything the plan doesn't specify.** The plan
  is `DESIGN.md`, `TODO.md` and each part's own `TODO.md`. If the work
  needs a design or behaviour choice they don't cover, stop and ask in
  chat, with a recommendation. Once it's agreed, write it down: how the
  system works goes in `DESIGN.md`, and how a part is built in its
  TODO. Don't decide it yourself and carry on. An agreed plan covers
  only what it lists: an extra attribute, method or convenience is a
  decision too, so ask before adding it.
- **How the system works goes only in `DESIGN.md`.** TODOs list the
  work and link to it, never repeat it, so the two can't drift apart.
  TODOs hold tasks only, not open questions.
- **The first line is the answer.** It's often the only line read, so
  make it the direct, precise answer to the exact question, true on its
  own. If the answer is "partly", say so and why in that line. Keep
  replies short; no walkthroughs unless asked.
- **Answer questions; don't act on them.** "So would you do X?" is a
  question, not a request to do X.
- **Comments are short and high-signal.** Write one only when it tells
  the reader something valuable the code doesn't: why, or what isn't
  obvious. Don't comment for the sake of documenting; no comment beats
  one that restates the code. One point each, on the line they explain.
  Don't argue against alternatives in comments; if that reasoning is
  worth keeping, it goes in a `.md`.
- **State costs plainly.** Give the real size of a change, in lines or
  files. Don't make a small change sound big, or count side issues
  against an option that it doesn't actually cause. If the reason for
  leaving something out is just that nothing needed it, say so.
- **Don't run sanitisers unless asked.** No ASan or UBSan builds or
  runs unless the user asks for one; they waste tokens. A build with
  no warnings, plus trying it by hand, is the check.
