
## อัปเดต v2.1 — PM แบบ Coordinator (เบาและไม่จุกจิก)

รอบนี้กำหนดเส้นทางรายงานเป็น **Worker → Reviewer → PM** โดย Worker แก้โค้ด/ทดสอบเป็นหลัก, Reviewer ประสาน review-fix loop เอง และ PM รับเพียงผลที่ผ่าน review หรือการตัดสินใจสำคัญ ไม่ต้องถามสถานะทุก turn และไม่ต้องสั่งงานผ่าน PM ทุกครั้งที่รีวิวพบ bug

เปลี่ยนผู้รับรีวิวในโปรเจกต์เดิมด้วย CLI (ไม่ต้องแก้ JSON เอง):

```powershell
agentorg role set backend-worker --reviewer-role technical-reviewer
agentorg role set frontend-worker --reviewer-role design-reviewer
```

หากต้องการใช้กับ Antigravity ที่เป็น PM: ทดสอบให้ Agent มีสิทธิ์รันคำสั่ง `hc --skill` และ `hc ls` บน environment เดียวกับ Herdr Core ด้วย; กรณีใช้จาก IDE ที่ไม่ได้เปิดภายใน Herdr จะไม่รับข้อความ `hc send` เป็น push notification ถึง PM โดยอัตโนมัติ ต้องมีการตรวจสถานะตอนเปิด PM กลับมา หรือใช้ watcher แยก

ติดตั้ง Skills (เลือกตัวที่เป็น PM):

```powershell
agentorg install --target claude --force
agentorg install --target codex --force
agentorg install --target antigravity --force
# หรือ agentorg install --target all --force
```

`--force` ใช้เพื่ออัปเดต Skill จากเวอร์ชันก่อนและจะเขียนทับโฟลเดอร์ Skill ที่ชื่อเดียวกัน **สำรองเวอร์ชันที่คุณเคยปรับแต่งก่อน** จากนั้นปิด/เปิด session PM ใหม่เพื่อให้โหลดคำสั่งใหม่ (ทีมที่กำลังรันอยู่จะยังไม่ถูก restart หรือเปลี่ยน prompt เดิมอัตโนมัติ)

**หมายเหตุ:** นโยบายนี้ยังไม่ได้เพิ่ม background fleet watcher; หาก PM หยุดรันไป ระบบไม่รับประกันว่าจะเริ่ม milestone ใหม่เองตลอด 24/7

# Herdr Agent Organization v2 — คู่มือภาษาไทย

โครงงานนี้เป็น **repo-ready open-source starter kit** สำหรับให้ PM agent ตัวใดก็ได้ (Claude หรือ Codex) โหลด skills แล้วสร้างทีมจาก provider/profile ที่ผู้ใช้ตั้งไว้ **โดยไม่ต้องเขียน prompt ยาวใหม่ทุกโปรเจกต์**

หลักการสำคัญ: Skill เป็นกฎการทำงาน, `.ai/TEAM.json` เป็นทีมประจำโปรเจกต์, `profiles.json` อยู่ในเครื่องคุณเท่านั้น, `.ai/STATE.md` เป็น checkpoint ที่ต้องตรวจเทียบกับ Herdr/Git/PR ทุกครั้ง

## ติดตั้ง

จากโฟลเดอร์ repo นี้:

```powershell
py -m pip install -e .
agentorg install --target both
```

Claude Code ใช้ `/agent-org-manager` ได้เมื่อ Skill โหลดแล้ว ส่วน Codex ให้เรียก Skill จากคำสั่งภาษาธรรมดา (`Use agent-org-manager skill`) การติดตั้ง **ไม่ได้เปิด agent ใด ๆ อัตโนมัติ**

## สร้างโปรเจกต์ใหม่

```powershell
cd C:\Code\your-project
agentorg init --template engineering --name your-project
```

เลือก template ได้ 3 แบบคือ `engineering`, `research`, `content` แก้ `.ai/PROJECT.md` และ `.ai/ROADMAP.md` ให้เป็นความจริงของงานนั้นก่อนใช้งาน

## ตั้ง Claude/Codex profile แบบไม่แชร์ credential

```powershell
agentorg profile add reviewer --provider claude --config-dir "C:\Users\YOU\.claude-work" --model opus --effort medium
agentorg profile add implementer --provider claude --config-dir "C:\Users\YOU\.claude-personal" --model sonnet --effort high
agentorg profile add designer --provider claude --config-dir "C:\Users\YOU\.claude-work" --model opus --effort medium
agentorg profile add frontend --provider codex --model gpt-6.2-sol --effort medium
```

แก้ path เป็นโฟลเดอร์ที่มีอยู่จริงและลงชื่อเข้าใช้ไว้แล้ว อย่าใส่ email/API key ลงใน repo หากใช้ Codex profile แยกให้เพิ่ม `--config-dir PATH` (ใช้ `CODEX_HOME`) หรือ `--native-profile NAME` (หากมี Codex config profile จริง)

```powershell
agentorg role list
agentorg role set backend-worker --profile implementer
agentorg role set frontend-worker --profile frontend
agentorg doctor
agentorg team plan
```

`team plan` เป็นเพียง preview. ถ้าเป็น software project ต้อง commit `.ai/TEAM.json` และเอกสารก่อนเริ่ม เพราะ worker จะอยู่ใน worktree ที่สร้างจาก commit:

```powershell
git add .ai QUESTION.md
git commit -m "Set up agent team"
agentorg team up --apply
agentorg team status
agentorg team send backend-worker "Read current requirements, implement one scoped task, run tests and report."
```

**ข้อสำคัญ:** `--apply` จะสร้าง agent processes จริง, Git worktree และ branch. PM/ผู้ใช้ควร review แผนก่อนเสมอ และการที่ agent ทำ PR เสร็จไม่ใช่สิทธิ์ให้ merge/release ได้เอง

## เกี่ยวกับตัว PM

- PM คือ Claude/Codex session ปัจจุบันของคุณ ไม่จำเป็นต้องมีโปรไฟล์ `pm` ใน `TEAM.json`
- PM อ่าน `hc --skill` เพื่อใช้ Herdr ตามเวอร์ชันที่ติดตั้งจริง
- Agent ที่เกิดจาก `agentorg team up --apply` จะเปิดเป็น Herdr terminals รอรับ task โดยใช้ local CLI/profile ที่ตั้งไว้
- Agent ที่ใช้ `--outlive-parent` อาจยังอยู่หลัง PM process จบ แต่ไม่ได้รับประกันการทำงาน 24/7 ในกรณีเครื่องดับหรือ server ไม่รัน
- PM ตัวใหม่ใช้ `/agent-org-recovery`, `agentorg team reconcile` และ Git/PR inspection เพื่อกู้ทีมโดยไม่สร้าง worker ซ้ำ
- การให้ Reviewer เขียนโค้ดเองต้องมี final verifier คนอื่น และห้าม merge/release โดยไม่ได้รับอนุญาต

## เปิดใช้กับ LayerDelta

มีตัวอย่าง `.ai/TEAM.json` ใน `examples/layerdelta/` ใช้ profile aliases `claude-work`, `claude-pro`, `codex-personal` โดย **ไม่มีบัญชีหรือรหัสจริง** ก่อนใช้ต้องเพิ่ม profile aliases ในเครื่องและตรวจว่า model รองรับจริง

## ขอบเขตของ v2 ที่สร้างครั้งนี้

มี CLI, skills, templates, profile isolation, preview, idempotent spawn check, worktree isolation และ tests. **ยังไม่ได้ทดสอบกับ Herdr process และบัญชีจริงบน Windows ของคุณ**; ยังไม่มี fleet watcher service ที่รันโดยตัวมันเอง, dashboard, auto-merge หรือระบบ restart PM อัตโนมัติ

เอกสารภาษาอังกฤษครบที่ [README.md](README.md) และสำหรับให้ Codex พัฒนาต่อดู [CODEX_HANDOFF.md](CODEX_HANDOFF.md)

## v2.1 — Coordinator-first PM (Worker > Reviewer > PM)

The PM only plans milestones, assigns task owners/reviewers, resolves blockers/decisions and receives **reviewer-verified milestone reports**. Workers implement/test and notify their paired reviewer directly; reviewers own feedback, QA and correction cycles. PM must not poll frequently or relay ordinary review comments. This is a **skill policy and initial agent prompt**, not a background watcher or guaranteed always-on scheduler.

The engineering template includes `reviewer_role` on worker roles, e.g. `backend-worker → technical-reviewer`. On new work, explicitly pair the worker with the reviewer. Users may override or remove the optional routing field, but a configured reviewer must exist and be enabled.

### Install skill for a PM host

```powershell
agentorg install --target claude       # ~/.claude/skills (or CLAUDE_CONFIG_DIR)
agentorg install --target codex        # ~/.agents/skills
agentorg install --target antigravity  # ~/.gemini/config/skills
agentorg install --target all          # all three
```

`both` remains the backwards-compatible Claude + Codex alias. When updating an older install, use `--force` **after checking for local custom edits**. Codex can invoke `$agent-org-manager`; Antigravity App/IDE supports `/agent-org-manager`. Skill discovery does not confer access to Herdr: the agent must have shell/tool permission to call `hc` in an environment connected to the running Herdr Core.

Antigravity can serve as an **interactive PM** through its skill and `hc` shell calls. v2.1 does **not** launch Antigravity as a Herdr worker (`agentorg profile add` intentionally supports `claude` and `codex` only), and a PM outside a Herdr terminal may not receive `hc send` push messages; reviewers should keep durable reports until it is invoked again.
