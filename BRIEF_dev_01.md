# 开发交底书 · 第 1 期

本文档是给 codex 的唯一上下文来源。你没有此前的对话记忆，所有你需要知道的事都在这里。

---

## 0. 这是什么项目

一个课程资料共享网站。学生上传笔记/真题/课件，别人能搜索、筛选、下载。

暂定形式：**纯本机运行的 Web 应用，零云端依赖**。用户在 Windows 上双击一个 .bat 文件就能启动，浏览器打开 localhost 就能用完整功能。

**本期明确不做云端**：不碰 Cloudflare、不碰任何外部 API、不注册任何账号、不部署。
**本期明确不做**：用户系统、登录注册、评论、点赞、私信、AI 检索、邮件发送、双机验证流程。

---

## 1. 技术栈（硬性要求，不要自行更换）

- **语言：Python 3**。检查系统已装的 Python 版本，用已有的，不要装新的。
- **Web 框架：只用 Python 标准库 `http.server`**。不要引入 Flask / FastAPI / Django。
- **数据库：SQLite**，用标准库 `sqlite3`。
- **文件存储：本地文件夹**。
- **前端：服务端直接吐 HTML 字符串**，配少量原生 JS，CSS 手写内联。不要引入 React、Vue、Tailwind、Vite、npm 或任何前端构建工具。
- **依赖：越少越好**。除以下两种情形外，一律用标准库：
  - 剥离 PDF/Office 元数据（见第 4 节）如果标准库做不到，允许引入，但必须先在本文件末尾记录并说明理由。
  - 其余情况一律不许 pip install。

选这套栈的理由：项目最终会交给一个正在自学 Python 的初学者维护，代码必须他能逐行读懂。任何"框架魔法"都是负债。

---

## 2. 数据库 Schema

以下 schema 是为了将来能平滑迁移到 Cloudflare D1（D1 就是 SQLite）而设计的。**请严格按照此结构建表，不要增删字段，不要改字段名。**

```sql
CREATE TABLE materials (
    id                 TEXT PRIMARY KEY,
    title              TEXT NOT NULL,
    description        TEXT,
    course_code        TEXT,
    course_name        TEXT,
    category           TEXT,          -- 笔记/真题/课件/教材/其他
    semester           TEXT,          -- 如 2026S1
    tags               TEXT,          -- JSON 数组字符串
    file_key           TEXT NOT NULL, -- 存储路径（主源）
    file_name          TEXT NOT NULL, -- 系统生成的规范文件名
    original_name      TEXT,          -- 原始文件名，仅管理员可见
    file_size          INTEGER,
    mime_type          TEXT,
    sha256             TEXT,
    uploader_note      TEXT,          -- 上传者昵称，可空
    upload_credential  TEXT,          -- 匿名凭证，非身份
    status             TEXT NOT NULL DEFAULT 'pending',  -- pending/approved/rejected/removed
    review_note        TEXT,
    reviewed_at        TEXT,
    reviewer           TEXT,
    downloads          INTEGER NOT NULL DEFAULT 0,
    views              INTEGER NOT NULL DEFAULT 0,
    ip_hmac            TEXT,
    created_at         TEXT NOT NULL,
    updated_at         TEXT NOT NULL
);

CREATE TABLE material_sources (
    material_id  TEXT,
    provider     TEXT,      -- r2 / github / local
    object_key   TEXT,
    size         INTEGER,
    sha256       TEXT,
    priority     INTEGER
);

CREATE TABLE credentials (
    credential     TEXT PRIMARY KEY,
    approved_count INTEGER NOT NULL DEFAULT 0,
    level          INTEGER NOT NULL DEFAULT 0,  -- 0 需审核 / 1 免审
    first_seen     TEXT
);

CREATE TABLE reports (
    id           TEXT PRIMARY KEY,
    material_id  TEXT NOT NULL,
    reason       TEXT,
    detail       TEXT,
    ip_hmac      TEXT,
    status       TEXT,
    created_at   TEXT NOT NULL
);

CREATE TABLE upload_events (
    ip_hmac     TEXT,
    credential  TEXT,
    created_at  TEXT
);

CREATE TABLE audit_log (
    id           TEXT PRIMARY KEY,
    material_id  TEXT,
    action       TEXT,
    reason       TEXT,
    actor        TEXT,
    created_at   TEXT NOT NULL
);
```

注意：`credentials` 和 `upload_events` 在本期**没有任何业务逻辑会用到**（免审逻辑和限流是后续版本的事）。仍然要建表，但不要为它们写业务逻辑。`material_sources` 同理——本期只写 `provider='local'` 的一条记录，不写多源逻辑。

---

## 3. 本期要实现的功能（P1 范围）

### 3.1 页面
1. **首页** `/` — 列出 status='approved' 的资料，按 created_at 倒序，分页（每页 20 条）
2. **搜索** — 按 title / course_code / description 模糊匹配，能在首页即时出结果（前端不做复杂交互，输入后回车或点按钮即可，不要做实时搜索）
3. **筛选** — 可按 course_code、category、semester 筛选，且可组合
4. **上传页** `/upload` — 拖入或选择文件、填写表单、提交
5. **详情页** `/material/<id>` — 显示完整元信息 + 下载次数 + 举报按钮
6. **下载** `/download/<id>` — 取回文件，downloads 计数 +1
7. **管理页** `/admin` — 需 token 进入；列表待审资料；能通过/拒绝/下架/恢复；能看举报列表
8. **关于页** `/about` — 放版权说明与投诉通道的占位文本

### 3.2 硬性规则
- 单文件上限 50MB。**前端校验 + 后端校验都要有**，绕过前端提交也必须被拒。
- 类型白名单：pdf / docx / pptx / xlsx / zip / png / jpg / md / txt / epub。同样前后端都校验。
- sha256 去重：同一文件二次上传，返回「已存在」并给出原资料链接。
- 上传后 `status='pending'`，不直接公开。
- 系统生成规范文件名存入 `file_name`；`original_name` 只在管理页可见。
- 举报累计 3 次（status 未处理的）→ 该资料 status 自动改为 'removed'，**文件仍留在磁盘上，只改状态**。
- 管理页的每个动作都要写入 `audit_log`。
- `/admin` 的 token 从环境变量或配置文件读取，不要硬编码在代码里。
- 空结果 / 加载中 / 出错，都要显示人话文案，不能白屏。

### 3.3 上传流程自动剥离元数据
上传时自动清除：PDF 与 Office 文档的作者/公司/修订记录元数据、图片的 EXIF。

**要求：这个功能必须写成可以单独调用的独立函数**，不要焊接在上传流程里。理由是要能单独喂一个带元数据的文件进去验证结果。

---

## 4. 交付要求

### 4.1 文件结构
结构由你决定，但要满足：
- 有一个 `start.bat`，双击就能启动服务并提示用户去浏览器打开哪个地址。
- 有一个 `README.md`，用中文写：怎么启动、怎么进管理页、代码各个文件是干什么的。
- 代码注释用中文。面向的读者是 Python 初学者。

### 4.2 启动方式
双击 `start.bat` → 启动服务 → 控制台打印出访问地址 → 用户打开浏览器。
不要要求用户敲命令行参数。

### 4.3 你要输出的内容
1. 完整的代码文件
2. 一份 `SELF_TEST.md`：你怎么验证自己写的东西是能跑的。必须包含**实际执行过的命令和真实输出**，不许写「应该可以」。如果你跑了测试，贴真实结果；如果某项没验证，明确写「未验证」。

---

## 5. 边界（不要越界）

- 不要建 git 仓库，不要 commit。仓库的建立由人类决定。
- 不要安装任何全局工具。
- 不要修改当前工作目录以外的任何文件。
- 不要为「将来接 Cloudflare」写任何适配代码。存储层现在就是本地文件夹，不要抽象成接口。
- 不要写测试框架（pytest 等）。验证靠 `SELF_TEST.md` 里手工执行的真实命令。
- 如果我的要求里有自相矛盾或技术上做不到的地方，**停下来在 SELF_TEST.md 里明确写出来**，不要自己猜一个方案糊过去。

---

## 6. 完成后

在 `SELF_TEST.md` 末尾列出：
1. 你认为已完成的
2. 你认为没做或做了但不确定的
3. 你发现的需求矛盾或坑
